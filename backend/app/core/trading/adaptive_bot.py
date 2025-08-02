"""
Adaptive Multi-Strategy Trading Bot - Dynamically allocates capital across strategies.
"""

import asyncio
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass, field

from app.core.trading.base import (
    MultiStrategyBot, TradingStrategy, Signal, Order, Trade, Position,
    OrderType, OrderSide, BotStatus
)
from app.core.trading.exchange import BinanceExchange
from app.core.trading.risk_manager import AdvancedRiskManager, RiskLimits
from app.core.trading.strategies.momentum_punch import MomentumPunchStrategy
from app.core.trading.strategies.value_punch import ValuePunchStrategy
from app.core.trading.strategies.breakout_punch import BreakoutPunchStrategy
from app.core.trading.strategies.trend_punch import TrendPunchStrategy
from app.data.manager import data_manager
from app.core.indicators.base import IndicatorManager
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class StrategyPerformance:
    """Track strategy performance metrics"""
    name: str
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    allocated_capital: float = 0.0
    current_allocation: float = 0.0
    signals_generated: int = 0
    signals_executed: int = 0
    confidence_scores: List[float] = field(default_factory=list)
    recent_trades: List[Trade] = field(default_factory=list)
    
    def update_metrics(self):
        """Update calculated metrics"""
        if self.trades_count > 0:
            self.win_rate = self.wins / self.trades_count
            
            if self.losses > 0:
                self.profit_factor = abs(self.avg_win * self.wins) / abs(self.avg_loss * self.losses)
            else:
                self.profit_factor = float('inf') if self.wins > 0 else 0.0
        
        if len(self.confidence_scores) > 0:
            self.avg_confidence = np.mean(self.confidence_scores)


class AdaptiveMultiStrategyBot(MultiStrategyBot):
    """
    Advanced multi-strategy bot that dynamically allocates capital
    based on strategy performance, market conditions, and risk metrics.
    """
    
    def __init__(
        self,
        bot_id: str,
        name: str,
        config: Dict[str, Any],
        symbols: List[str],
        timeframes: List[str] = None
    ):
        # Initialize exchange
        exchange = BinanceExchange(paper_trading=config.get('paper_trading', True))
        
        # Initialize risk manager
        risk_limits = RiskLimits(
            max_position_size=config.get('max_position_size', 0.1),
            max_portfolio_risk=config.get('max_portfolio_risk', 0.02),
            max_daily_loss=config.get('max_daily_loss', 0.05),
            max_drawdown=config.get('max_drawdown', 0.15),
            max_open_positions=config.get('max_open_positions', 5),
            max_trades_per_day=config.get('max_trades_per_day', 10)
        )
        risk_manager = AdvancedRiskManager(risk_limits)
        
        # Initialize strategies
        strategies = [
            MomentumPunchStrategy(config.get('momentum_params')),
            ValuePunchStrategy(config.get('value_params')),
            BreakoutPunchStrategy(config.get('breakout_params')),
            TrendPunchStrategy(config.get('trend_params'))
        ]
        
        # Initial equal allocation
        initial_allocation = {strategy.name: 0.25 for strategy in strategies}
        
        super().__init__(
            bot_id, name, exchange, risk_manager, strategies,
            initial_allocation, config
        )
        
        # Bot-specific configuration
        self.symbols = symbols
        self.timeframes = timeframes or ['1h', '4h']
        self.update_interval = config.get('update_interval', 300)  # 5 minutes
        self.rebalance_interval = config.get('rebalance_interval', 3600)  # 1 hour
        
        # Performance tracking
        self.strategy_performance = {
            strategy.name: StrategyPerformance(name=strategy.name)
            for strategy in strategies
        }
        
        # Market condition detection
        self.market_conditions = {
            'trend': 'neutral',  # bullish, bearish, neutral
            'volatility': 'normal',  # low, normal, high
            'volume': 'normal',  # low, normal, high
            'correlation': 'normal'  # low, normal, high
        }
        
        # Adaptive parameters
        self.allocation_decay = config.get('allocation_decay', 0.95)  # Memory decay
        self.performance_lookback = config.get('performance_lookback', 30)  # Days
        self.min_allocation = config.get('min_allocation', 0.05)  # 5% minimum
        self.max_allocation = config.get('max_allocation', 0.6)   # 60% maximum
        
        # Control flags
        self._running = False
        self._last_update = None
        self._last_rebalance = None
        
        # Initialize indicator manager
        self.indicator_manager = IndicatorManager()
    
    async def start(self):
        """Start the adaptive trading bot"""
        if self._running:
            logger.warning(f"Bot {self.name} is already running")
            return
        
        try:
            # Try to restore previous state
            restored = await self.restore_state()
            if restored:
                logger.info(f"Restored previous state for bot {self.name}")
            
            # Connect to exchange
            if not await self.exchange.connect():
                raise Exception("Failed to connect to exchange")
            
            # Validate strategies
            for strategy in self.strategies:
                if not strategy.validate_parameters():
                    raise Exception(f"Invalid parameters for strategy {strategy.name}")
            
            self.status = BotStatus.RUNNING
            self._running = True
            self._last_update = datetime.utcnow()
            self._last_rebalance = datetime.utcnow()
            
            logger.info(f"Started adaptive bot {self.name} with {len(self.strategies)} strategies")
            
            # Start main trading loop
            await self._main_loop()
            
        except Exception as e:
            logger.error(f"Error starting bot {self.name}: {e}")
            self.status = BotStatus.ERROR
            await self._emit_error(f"Startup error: {e}")
    
    async def stop(self):
        """Stop the trading bot"""
        self._running = False
        self.status = BotStatus.STOPPED
        
        # Save final state
        await self.save_state()
        logger.info(f"Saved final state for bot {self.name}")
        
        # Close all open positions
        await self._close_all_positions("Bot stopped")
        
        # Disconnect from exchange
        await self.exchange.disconnect()
        
        logger.info(f"Stopped adaptive bot {self.name}")
    
    async def pause(self):
        """Pause the trading bot"""
        self.status = BotStatus.PAUSED
        logger.info(f"Paused adaptive bot {self.name}")
    
    async def resume(self):
        """Resume the trading bot"""
        if self.status == BotStatus.PAUSED:
            self.status = BotStatus.RUNNING
            logger.info(f"Resumed adaptive bot {self.name}")
    
    async def _main_loop(self):
        """Main trading loop"""
        last_save_time = datetime.utcnow()
        save_interval = 300  # Save state every 5 minutes
        
        while self._running:
            try:
                current_time = datetime.utcnow()
                
                # Update portfolio
                await self._update_portfolio()
                
                # Check if it's time to rebalance allocations
                if (current_time - self._last_rebalance).total_seconds() >= self.rebalance_interval:
                    await self._rebalance_allocations()
                    self._last_rebalance = current_time
                
                # Process signals if bot is running (not paused)
                if self.status == BotStatus.RUNNING:
                    await self._process_signals()
                
                # Update performance metrics
                await self._update_performance_metrics()
                
                # Save state periodically
                if (current_time - last_save_time).total_seconds() >= save_interval:
                    await self.save_state()
                    last_save_time = current_time
                    logger.info(f"Bot state saved for {self.bot_id}")
                
                # Sleep until next update
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await self._emit_error(f"Main loop error: {e}")
                
                # Try to save state on error
                try:
                    await self.save_state()
                except:
                    pass
                
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _update_portfolio(self):
        """Update portfolio state from exchange"""
        try:
            # Get current positions
            positions = await self.exchange.get_positions()
            self.portfolio.positions = positions
            
            # Get current balance
            balance = await self.exchange.get_balance()
            self.portfolio.cash = balance.get('USDT', 0)
            
            # Update portfolio value with current prices
            current_prices = {}
            for symbol in self.symbols:
                try:
                    ticker = await self.exchange.get_ticker(symbol)
                    current_prices[symbol] = ticker['last']
                except:
                    continue
            
            self.portfolio.update_portfolio_value(current_prices)
            
        except Exception as e:
            logger.error(f"Error updating portfolio: {e}")
    
    async def _process_signals(self):
        """Process signals from all strategies"""
        all_signals = []
        
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                try:
                    # Fetch market data
                    df = await data_manager.fetch_ohlcv(
                        symbol=symbol,
                        timeframe=timeframe,
                        limit=200
                    )
                    
                    if df.empty or len(df) < 100:
                        continue
                    
                    # Calculate indicators
                    indicators = await self.indicator_manager.calculate_all(df)
                    
                    # Generate signals from each strategy
                    for strategy in self.strategies:
                        if not strategy.active:
                            continue
                        
                        try:
                            signals = await strategy.generate_signals(symbol, df, indicators)
                            
                            for signal in signals:
                                # Weight signal by strategy allocation
                                allocation = self.strategy_allocations.get(strategy.name, 0)
                                signal.confidence *= allocation  # Reduce confidence for lower allocation
                                
                                # Track signal generation
                                self.strategy_performance[strategy.name].signals_generated += 1
                                all_signals.append(signal)
                                
                        except Exception as e:
                            logger.error(f"Error generating signals for {strategy.name}: {e}")
                
                except Exception as e:
                    logger.error(f"Error processing {symbol} {timeframe}: {e}")
        
        # Filter and execute best signals
        await self._execute_signals(all_signals)
    
    async def _execute_signals(self, signals: List[Signal]):
        """Execute the best signals based on confidence and risk"""
        if not signals:
            return
        
        # Sort signals by confidence score
        signals.sort(key=lambda x: x.confidence, reverse=True)
        
        # Process top signals
        for signal in signals:
            try:
                # Check if we can trade this signal
                if not await self._can_execute_signal(signal):
                    continue
                
                # Calculate position size
                position_size = self.risk_manager.calculate_position_size(
                    signal, self.portfolio, self.config.get('risk_per_trade', 0.01)
                )
                
                if position_size <= 0:
                    continue
                
                # Create and execute order
                order = Order(
                    id=str(uuid.uuid4()),
                    symbol=signal.symbol,
                    type=OrderType.MARKET,
                    side=OrderSide.BUY if signal.direction == 'buy' else OrderSide.SELL,
                    amount=position_size,
                    price=signal.price
                )
                
                # Validate order with risk manager
                if not self.risk_manager.validate_order(order, self.portfolio):
                    continue
                
                # Execute order
                order_id = await self.exchange.place_order(order)
                
                if order_id:
                    # Track execution
                    strategy_name = signal.strategy
                    self.strategy_performance[strategy_name].signals_executed += 1
                    
                    # Emit signal event
                    await self._emit_signal(signal)
                    
                    logger.info(f"Executed signal: {signal.direction} {signal.symbol} - Strategy: {strategy_name}")
                    
                    # Limit to one signal per update cycle for safety
                    break
                
            except Exception as e:
                logger.error(f"Error executing signal: {e}")
    
    async def _can_execute_signal(self, signal: Signal) -> bool:
        """Check if signal can be executed"""
        # Check if we already have a position in this symbol
        if signal.symbol in self.portfolio.positions:
            return False
        
        # Check if signal meets minimum confidence
        if signal.confidence < 0.5:  # Adjusted for allocation weighting
            return False
        
        # Check strategy allocation
        allocation = self.strategy_allocations.get(signal.strategy, 0)
        if allocation < self.min_allocation:
            return False
        
        return True
    
    async def _rebalance_allocations(self):
        """Dynamically rebalance strategy allocations based on performance"""
        try:
            logger.info("Rebalancing strategy allocations...")
            
            # Update market conditions
            await self._update_market_conditions()
            
            # Calculate new allocations based on performance and market conditions
            new_allocations = await self._calculate_optimal_allocations()
            
            # Apply allocation changes gradually
            for strategy_name, new_allocation in new_allocations.items():
                current_allocation = self.strategy_allocations.get(strategy_name, 0.25)
                
                # Gradual change to avoid dramatic shifts
                change = (new_allocation - current_allocation) * 0.3  # 30% of desired change
                self.strategy_allocations[strategy_name] = max(
                    self.min_allocation,
                    min(self.max_allocation, current_allocation + change)
                )
            
            # Normalize allocations to sum to 1.0
            total_allocation = sum(self.strategy_allocations.values())
            if total_allocation > 0:
                for strategy_name in self.strategy_allocations:
                    self.strategy_allocations[strategy_name] /= total_allocation
            
            logger.info(f"New allocations: {self.strategy_allocations}")
            
        except Exception as e:
            logger.error(f"Error rebalancing allocations: {e}")
    
    async def _calculate_optimal_allocations(self) -> Dict[str, float]:
        """Calculate optimal strategy allocations"""
        allocations = {}
        
        # Base scores for each strategy
        strategy_scores = {}
        
        for strategy_name, perf in self.strategy_performance.items():
            score = 0.0
            
            # Performance-based scoring
            if perf.trades_count >= 5:  # Minimum trades for meaningful stats
                # Profit factor weight (40%)
                if perf.profit_factor > 0:
                    score += min(perf.profit_factor / 2.0, 1.0) * 0.4
                
                # Win rate weight (25%)
                score += perf.win_rate * 0.25
                
                # Sharpe ratio weight (20%)
                if perf.sharpe_ratio > 0:
                    score += min(perf.sharpe_ratio / 2.0, 1.0) * 0.2
                
                # Max drawdown penalty (15%)
                drawdown_score = max(0, 1 - perf.max_drawdown / 0.3)  # Penalize >30% drawdown
                score += drawdown_score * 0.15
                
            else:
                # Not enough trades - use moderate score
                score = 0.5
            
            # Market condition adjustments
            score *= self._get_market_condition_multiplier(strategy_name)
            
            # Recent performance boost/penalty
            if len(perf.recent_trades) >= 3:
                recent_pnl = sum(trade.pnl for trade in perf.recent_trades[-5:])
                if recent_pnl > 0:
                    score *= 1.1  # 10% boost for recent profits
                else:
                    score *= 0.9  # 10% penalty for recent losses
            
            strategy_scores[strategy_name] = max(0.1, score)  # Minimum score
        
        # Convert scores to allocations
        total_score = sum(strategy_scores.values())
        
        if total_score > 0:
            for strategy_name, score in strategy_scores.items():
                allocations[strategy_name] = score / total_score
        else:
            # Fallback to equal allocation
            allocations = {name: 0.25 for name in strategy_scores.keys()}
        
        return allocations
    
    def _get_market_condition_multiplier(self, strategy_name: str) -> float:
        """Get market condition multiplier for strategy"""
        multiplier = 1.0
        
        # Adjust based on market conditions
        if strategy_name == 'momentum_punch':
            if self.market_conditions['trend'] in ['bullish', 'bearish']:
                multiplier *= 1.2  # Momentum works better in trending markets
            if self.market_conditions['volatility'] == 'high':
                multiplier *= 1.1
                
        elif strategy_name == 'value_punch':
            if self.market_conditions['trend'] == 'neutral':
                multiplier *= 1.2  # Value works better in ranging markets
            if self.market_conditions['volatility'] == 'low':
                multiplier *= 0.9  # Value needs some volatility
                
        elif strategy_name == 'breakout_punch':
            if self.market_conditions['volatility'] == 'low':
                multiplier *= 1.3  # Breakouts work better after low volatility
            if self.market_conditions['volume'] == 'high':
                multiplier *= 1.1
                
        elif strategy_name == 'trend_punch':
            if self.market_conditions['trend'] in ['bullish', 'bearish']:
                multiplier *= 1.3  # Trend following needs clear trends
            if self.market_conditions['trend'] == 'neutral':
                multiplier *= 0.7
        
        return multiplier
    
    async def _update_market_conditions(self):
        """Update market condition assessment"""
        try:
            # Analyze market across all symbols
            trend_scores = []
            volatility_scores = []
            volume_scores = []
            
            for symbol in self.symbols:
                try:
                    df = await data_manager.fetch_ohlcv(symbol, '4h', limit=50)
                    if df.empty:
                        continue
                    
                    # Trend analysis
                    sma_20 = df['close'].rolling(20).mean()
                    sma_50 = df['close'].rolling(50).mean()
                    
                    if len(sma_20) >= 20 and len(sma_50) >= 50:
                        current_price = df['close'].iloc[-1]
                        if current_price > sma_20.iloc[-1] > sma_50.iloc[-1]:
                            trend_scores.append(1)  # Bullish
                        elif current_price < sma_20.iloc[-1] < sma_50.iloc[-1]:
                            trend_scores.append(-1)  # Bearish
                        else:
                            trend_scores.append(0)  # Neutral
                    
                    # Volatility analysis (ATR)
                    high_low = df['high'] - df['low']
                    atr = high_low.rolling(14).mean()
                    current_atr = atr.iloc[-1] / df['close'].iloc[-1]
                    
                    if current_atr > 0.05:  # 5%
                        volatility_scores.append(1)  # High
                    elif current_atr < 0.02:  # 2%
                        volatility_scores.append(-1)  # Low
                    else:
                        volatility_scores.append(0)  # Normal
                    
                    # Volume analysis
                    volume_ma = df['volume'].rolling(20).mean()
                    current_volume_ratio = df['volume'].iloc[-1] / volume_ma.iloc[-1]
                    
                    if current_volume_ratio > 1.3:
                        volume_scores.append(1)  # High
                    elif current_volume_ratio < 0.7:
                        volume_scores.append(-1)  # Low
                    else:
                        volume_scores.append(0)  # Normal
                
                except Exception:
                    continue
            
            # Aggregate scores
            if trend_scores:
                avg_trend = np.mean(trend_scores)
                if avg_trend > 0.3:
                    self.market_conditions['trend'] = 'bullish'
                elif avg_trend < -0.3:
                    self.market_conditions['trend'] = 'bearish'
                else:
                    self.market_conditions['trend'] = 'neutral'
            
            if volatility_scores:
                avg_volatility = np.mean(volatility_scores)
                if avg_volatility > 0.3:
                    self.market_conditions['volatility'] = 'high'
                elif avg_volatility < -0.3:
                    self.market_conditions['volatility'] = 'low'
                else:
                    self.market_conditions['volatility'] = 'normal'
            
            if volume_scores:
                avg_volume = np.mean(volume_scores)
                if avg_volume > 0.3:
                    self.market_conditions['volume'] = 'high'
                elif avg_volume < -0.3:
                    self.market_conditions['volume'] = 'low'
                else:
                    self.market_conditions['volume'] = 'normal'
            
        except Exception as e:
            logger.error(f"Error updating market conditions: {e}")
    
    async def _update_performance_metrics(self):
        """Update strategy performance metrics"""
        for strategy_name, perf in self.strategy_performance.items():
            # Update from recent trades
            strategy_trades = [
                trade for trade in self.portfolio.trades
                if trade.strategy == strategy_name
            ]
            
            if strategy_trades:
                perf.trades_count = len(strategy_trades)
                perf.wins = sum(1 for trade in strategy_trades if trade.pnl > 0)
                perf.losses = perf.trades_count - perf.wins
                perf.total_pnl = sum(trade.pnl for trade in strategy_trades)
                
                if perf.wins > 0:
                    perf.avg_win = np.mean([trade.pnl for trade in strategy_trades if trade.pnl > 0])
                
                if perf.losses > 0:
                    perf.avg_loss = np.mean([trade.pnl for trade in strategy_trades if trade.pnl < 0])
                
                # Keep recent trades (last 10)
                perf.recent_trades = strategy_trades[-10:]
                
                # Update calculated metrics
                perf.update_metrics()
    
    async def _close_all_positions(self, reason: str):
        """Close all open positions"""
        for symbol, position in self.portfolio.positions.items():
            try:
                order = Order(
                    id=str(uuid.uuid4()),
                    symbol=symbol,
                    type=OrderType.MARKET,
                    side=OrderSide.SELL if position.side == 'long' else OrderSide.BUY,
                    amount=position.size
                )
                
                await self.exchange.place_order(order)
                logger.info(f"Closed position in {symbol}: {reason}")
                
            except Exception as e:
                logger.error(f"Error closing position in {symbol}: {e}")
    
    def get_detailed_status(self) -> Dict[str, Any]:
        """Get detailed bot status including strategy performance"""
        base_status = self.get_status()
        
        return {
            **base_status,
            'strategy_allocations': self.strategy_allocations,
            'strategy_performance': {
                name: {
                    'trades_count': perf.trades_count,
                    'win_rate': perf.win_rate,
                    'profit_factor': perf.profit_factor,
                    'total_pnl': perf.total_pnl,
                    'current_allocation': perf.current_allocation,
                    'signals_generated': perf.signals_generated,
                    'signals_executed': perf.signals_executed
                }
                for name, perf in self.strategy_performance.items()
            },
            'market_conditions': self.market_conditions,
            'symbols': self.symbols,
            'timeframes': self.timeframes,
            'last_rebalance': self._last_rebalance.isoformat() if self._last_rebalance else None
        }