import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import uuid
from dataclasses import dataclass, field

from app.data.manager import data_manager
from app.core.indicators.base import IndicatorManager
from app.core.signals.generator import SignalGenerator
from app.core.backtest.metrics import BacktestMetrics
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class Trade:
    """Represents a single trade"""
    id: str
    symbol: str
    direction: str  # 'long' or 'short'
    entry_price: float
    entry_time: datetime
    size: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    profit: float = 0
    profit_pct: float = 0
    commission: float = 0
    slippage: float = 0
    
    @property
    def is_open(self) -> bool:
        return self.exit_price is None
    
    @property
    def duration(self) -> Optional[timedelta]:
        if self.exit_time:
            return self.exit_time - self.entry_time
        return None


@dataclass
class Portfolio:
    """Manages portfolio state during backtest"""
    initial_capital: float
    cash: float
    positions: Dict[str, Trade] = field(default_factory=dict)
    closed_trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)
    
    @property
    def total_value(self) -> float:
        """Calculate total portfolio value"""
        position_value = sum(
            trade.size * trade.entry_price for trade in self.positions.values()
        )
        return self.cash + position_value
    
    @property
    def open_positions(self) -> int:
        return len(self.positions)
    
    def record_equity(self, timestamp: datetime, current_prices: Dict[str, float]):
        """Record current equity value"""
        # Calculate position values at current prices
        position_value = 0
        for symbol, trade in self.positions.items():
            current_price = current_prices.get(symbol, trade.entry_price)
            # Ensure all values are not None
            if current_price is None:
                current_price = trade.entry_price
            if trade.entry_price is None or trade.size is None:
                logger.warning(f"Invalid trade values for {symbol}: entry_price={trade.entry_price}, size={trade.size}")
                continue
                
            if trade.direction == 'long':
                position_value += trade.size * current_price
            else:  # short
                position_value += trade.size * (2 * trade.entry_price - current_price)
        
        total_equity = self.cash + position_value
        self.equity_curve.append(total_equity)
        self.timestamps.append(timestamp)


class BacktestEngine:
    """Event-driven backtesting engine"""
    
    def __init__(self):
        self.indicator_manager = IndicatorManager()
        self.signal_generator = SignalGenerator()
        self.metrics_calculator = BacktestMetrics()
        self.results_cache = {}
    
    async def run(
        self,
        symbol: str,
        strategy: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 10000,
        position_size: float = 0.1,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        timeframe: str = "1h",
        commission: float = 0.001,
        slippage: float = 0.0005
    ) -> Dict[str, Any]:
        """Run backtest for a single strategy"""
        
        backtest_id = str(uuid.uuid4())
        logger.info(f"Starting backtest {backtest_id} for {symbol} using {strategy}")
        
        try:
            # Fetch historical data
            df = await data_manager.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                start_time=start_date,
                end_time=end_date
            )
            
            if df.empty or len(df) < 50:
                raise ValueError("Insufficient data for backtesting")
            
            # Initialize portfolio
            portfolio = Portfolio(
                initial_capital=initial_capital,
                cash=initial_capital
            )
            
            # Track metrics
            all_signals = []
            
            # Process each candle
            for i in range(50, len(df)):  # Start after warmup period
                current_time = df.index[i]
                current_candle = df.iloc[i]
                historical_data = df.iloc[:i+1]
                
                # Update open positions
                self._update_positions(
                    portfolio, current_candle, symbol,
                    commission, slippage
                )
                
                # Check for new signals
                if portfolio.open_positions == 0:  # Only if no open position
                    # Calculate indicators
                    indicators = await self.indicator_manager.calculate_all(historical_data)
                    
                    # Generate signals for specific strategy
                    signals = await self._generate_strategy_signals(
                        strategy, symbol, timeframe, historical_data, indicators
                    )
                    
                    if signals:
                        signal = signals[0]  # Take highest confidence signal
                        all_signals.append(signal)
                        
                        # Execute trade
                        self._execute_trade(
                            portfolio, signal, current_candle,
                            position_size, stop_loss, take_profit,
                            commission, slippage
                        )
                
                # Record equity
                portfolio.record_equity(current_time, {symbol: current_candle['close']})
            
            # Close any remaining positions
            self._close_all_positions(
                portfolio, df.iloc[-1], symbol,
                commission, slippage, "End of backtest"
            )
            
            # Calculate metrics
            metrics = self.metrics_calculator.calculate(
                portfolio, initial_capital
            )
            
            # Prepare results
            results = {
                "backtest_id": backtest_id,
                "symbol": symbol,
                "strategy": strategy,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": (end_date - start_date).days
                },
                "parameters": {
                    "initial_capital": initial_capital,
                    "position_size": position_size,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "commission": commission,
                    "slippage": slippage
                },
                "metrics": metrics,
                "trades": [self._trade_to_dict(t) for t in portfolio.closed_trades],
                "equity_curve": {
                    "timestamps": [t.isoformat() for t in portfolio.timestamps],
                    "values": portfolio.equity_curve
                },
                "signals_generated": len(all_signals),
                "data_points": len(df)
            }
            
            # Cache results
            self.results_cache[backtest_id] = results
            
            return results
            
        except Exception as e:
            logger.error(f"Backtest error: {e}")
            raise
    
    def _update_positions(
        self,
        portfolio: Portfolio,
        current_candle: pd.Series,
        symbol: str,
        commission: float,
        slippage: float
    ):
        """Update open positions with current prices"""
        if symbol not in portfolio.positions:
            return
        
        trade = portfolio.positions[symbol]
        current_price = current_candle['close']
        
        # Check stop loss
        if trade.stop_loss:
            if (trade.direction == 'long' and current_candle['low'] <= trade.stop_loss) or \
               (trade.direction == 'short' and current_candle['high'] >= trade.stop_loss):
                exit_price = trade.stop_loss * (1 - (slippage if slippage is not None else 0))
                self._close_position(
                    portfolio, symbol, exit_price,
                    pd.Timestamp(current_candle.name),
                    commission, "Stop loss"
                )
                return
        
        # Check take profit
        if trade.take_profit:
            if (trade.direction == 'long' and current_candle['high'] >= trade.take_profit) or \
               (trade.direction == 'short' and current_candle['low'] <= trade.take_profit):
                exit_price = trade.take_profit * (1 + (slippage if slippage is not None else 0))
                self._close_position(
                    portfolio, symbol, exit_price,
                    pd.Timestamp(current_candle.name),
                    commission, "Take profit"
                )
    
    def _execute_trade(
        self,
        portfolio: Portfolio,
        signal: Any,  # Signal object from generator
        current_candle: pd.Series,
        position_size: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        commission: float,
        slippage: float
    ):
        """Execute a trade based on signal"""
        # Calculate position size
        position_value = portfolio.cash * position_size
        entry_price = current_candle['close'] * (1 + (slippage if slippage is not None else 0))
        size = position_value / entry_price
        
        # Calculate commission
        trade_commission = position_value * commission
        
        # Ensure we have enough cash
        if portfolio.cash < position_value + trade_commission:
            return
        
        # Create trade
        trade = Trade(
            id=str(uuid.uuid4()),
            symbol=signal.symbol if hasattr(signal, 'symbol') else current_candle.name,
            direction='long' if signal.direction == 'buy' else 'short',
            entry_price=entry_price,
            entry_time=pd.Timestamp(current_candle.name) if hasattr(current_candle, 'name') else datetime.now(),
            size=size,
            stop_loss=signal.stop_loss if hasattr(signal, 'stop_loss') else 
                     (entry_price * (1 - stop_loss) if stop_loss is not None else None),
            take_profit=(signal.take_profit_levels[0] if hasattr(signal, 'take_profit_levels') and 
                        signal.take_profit_levels and len(signal.take_profit_levels) > 0 else
                       (entry_price * (1 + take_profit) if take_profit is not None else None)),
            commission=trade_commission
        )
        
        # Update portfolio
        portfolio.cash -= (position_value + trade_commission)
        portfolio.positions[trade.symbol] = trade
    
    def _close_position(
        self,
        portfolio: Portfolio,
        symbol: str,
        exit_price: float,
        exit_time: datetime,
        commission: float,
        exit_reason: str
    ):
        """Close an open position"""
        if symbol not in portfolio.positions:
            return
        
        trade = portfolio.positions[symbol]
        trade.exit_price = exit_price
        trade.exit_time = exit_time
        trade.exit_reason = exit_reason
        
        # Validate prices are not None
        if exit_price is None or trade.entry_price is None or trade.size is None:
            logger.error(f"Invalid price values in trade: exit_price={exit_price}, entry_price={trade.entry_price}, size={trade.size}")
            trade.profit = 0
        else:
            # Calculate profit/loss
            if trade.direction == 'long':
                trade.profit = (exit_price - trade.entry_price) * trade.size
            else:  # short
                trade.profit = (trade.entry_price - exit_price) * trade.size
        
        # Ensure profit is not None before any operations
        if trade.profit is None:
            trade.profit = 0
            
        # Calculate profit percentage safely
        entry_value = trade.entry_price * trade.size
        if entry_value != 0:
            trade.profit_pct = (trade.profit / entry_value) * 100
        else:
            trade.profit_pct = 0
        
        # Apply exit commission
        exit_commission = exit_price * trade.size * commission
        
        # Ensure commission is not None before addition
        if trade.commission is None:
            trade.commission = 0
            
        trade.commission += exit_commission
        
        # Safely subtract commission from profit
        if trade.profit is not None and trade.commission is not None:
            trade.profit -= trade.commission
        elif trade.commission is not None:
            trade.profit = -trade.commission
        else:
            trade.profit = 0
        
        # Update portfolio
        portfolio.cash += (exit_price * trade.size - exit_commission)
        portfolio.closed_trades.append(trade)
        del portfolio.positions[symbol]
    
    def _close_all_positions(
        self,
        portfolio: Portfolio,
        current_candle: pd.Series,
        symbol: str,
        commission: float,
        slippage: float,
        reason: str
    ):
        """Close all open positions"""
        for sym in list(portfolio.positions.keys()):
            exit_price = current_candle['close'] * (1 - slippage)
            self._close_position(
                portfolio, sym, exit_price,
                pd.Timestamp(current_candle.name),
                commission, reason
            )
    
    async def _generate_strategy_signals(
        self,
        strategy: str,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        indicators: Dict
    ) -> List[Any]:
        """Generate signals for a specific strategy"""
        # This is a simplified version - in production would use the actual signal generator
        signals = []
        
        if strategy == "momentum_punch":
            # Check momentum conditions
            if 'rsi' in indicators and 'macd' in indicators:
                rsi = indicators['rsi'].values.iloc[-1]
                macd = indicators['macd'].values.iloc[-1]
                
                if 40 < rsi < 60 and macd > 0:
                    # Create a mock signal
                    class MockSignal:
                        def __init__(self):
                            self.symbol = symbol
                            self.direction = 'buy'
                            self.confidence = 0.7
                    
                    signals.append(MockSignal())
        
        return signals
    
    def _trade_to_dict(self, trade: Trade) -> Dict:
        """Convert trade to dictionary"""
        return {
            "id": trade.id,
            "symbol": trade.symbol,
            "direction": trade.direction,
            "entry_price": trade.entry_price if trade.entry_price is not None else 0,
            "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
            "exit_price": trade.exit_price if trade.exit_price is not None else 0,
            "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
            "size": trade.size if trade.size is not None else 0,
            "profit": trade.profit if trade.profit is not None else 0,
            "profit_pct": trade.profit_pct if trade.profit_pct is not None else 0,
            "commission": trade.commission if trade.commission is not None else 0,
            "exit_reason": trade.exit_reason,
            "duration": str(trade.duration) if trade.duration else None
        }
    
    async def optimize(
        self,
        symbol: str,
        strategy: str,
        start_date: datetime,
        end_date: datetime,
        optimization_target: str = "sharpe_ratio"
    ) -> Dict[str, Any]:
        """Optimize strategy parameters"""
        # This is a placeholder - full implementation would use optimization algorithms
        logger.info(f"Optimizing {strategy} for {symbol}")
        
        # Return sample optimized parameters
        return {
            "strategy": strategy,
            "optimized_params": {
                "position_size": 0.15,
                "stop_loss": 0.015,
                "take_profit": 0.03
            },
            "expected_performance": {
                "sharpe_ratio": 1.5,
                "max_drawdown": -0.15,
                "win_rate": 0.55
            }
        }
    
    async def get_results(self, backtest_id: str) -> Optional[Dict[str, Any]]:
        """Get cached backtest results"""
        return self.results_cache.get(backtest_id)
    
    async def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent backtest history"""
        # Return recent cached results
        results = list(self.results_cache.values())
        results.sort(key=lambda x: x.get('period', {}).get('end', ''), reverse=True)
        return results[:limit]