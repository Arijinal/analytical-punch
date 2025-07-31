"""
Paper Trading Engine - Safe testing environment for trading strategies.
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
import json

from app.core.trading.base import (
    Order, OrderType, OrderSide, OrderStatus, Position, Trade, Portfolio, Signal
)
from app.core.trading.exchange import BinanceExchange
from app.data.manager import data_manager
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class PaperAccount:
    """Paper trading account state"""
    account_id: str
    initial_balance: float
    current_balance: float
    positions: Dict[str, Position] = field(default_factory=dict)
    orders: Dict[str, Order] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Performance metrics
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    max_balance: float = 0.0
    max_drawdown: float = 0.0
    trades_count: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Settings
    commission_rate: float = 0.001  # 0.1%
    slippage_rate: float = 0.0005   # 0.05%
    realistic_fills: bool = True    # Simulate realistic order fills
    
    def calculate_metrics(self):
        """Calculate account performance metrics"""
        self.trades_count = len(self.trades)
        
        if self.trades_count > 0:
            self.winning_trades = sum(1 for trade in self.trades if trade.pnl > 0)
            self.losing_trades = self.trades_count - self.winning_trades
            self.total_pnl = sum(trade.pnl for trade in self.trades)
            
            if self.initial_balance > 0:
                self.total_return_pct = (self.current_balance - self.initial_balance) / self.initial_balance * 100
        
        # Update max balance and drawdown
        if self.current_balance > self.max_balance:
            self.max_balance = self.current_balance
        
        if self.max_balance > 0:
            self.max_drawdown = max(self.max_drawdown, (self.max_balance - self.current_balance) / self.max_balance)


class PaperTradingEngine:
    """
    Paper trading engine that simulates real trading with realistic
    market conditions, slippage, and commission costs.
    """
    
    def __init__(self, exchange: BinanceExchange):
        self.exchange = exchange
        self.accounts: Dict[str, PaperAccount] = {}
        self.active_simulations: Dict[str, bool] = {}
        
        # Market simulation parameters
        self.price_cache: Dict[str, Dict] = {}
        self.order_book_cache: Dict[str, Dict] = {}
        self.last_price_update: Dict[str, datetime] = {}
        
        # Simulation settings
        self.update_interval = 5  # seconds
        self.realistic_slippage = True
        self.simulate_partial_fills = True
        self.simulate_order_rejections = True
        self.max_slippage = 0.01  # 1%
        
        # Performance tracking
        self.total_simulated_trades = 0
        self.successful_simulations = 0
    
    async def create_account(
        self, 
        initial_balance: float = 100000,
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005,
        realistic_fills: bool = True
    ) -> str:
        """Create a new paper trading account"""
        
        account_id = str(uuid.uuid4())
        
        account = PaperAccount(
            account_id=account_id,
            initial_balance=initial_balance,
            current_balance=initial_balance,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
            realistic_fills=realistic_fills
        )
        
        account.max_balance = initial_balance
        
        self.accounts[account_id] = account
        logger.info(f"Created paper trading account {account_id} with ${initial_balance:,.2f}")
        
        return account_id
    
    async def delete_account(self, account_id: str) -> bool:
        """Delete a paper trading account"""
        if account_id in self.accounts:
            # Stop any active simulations
            self.active_simulations[account_id] = False
            
            # Remove account
            del self.accounts[account_id]
            logger.info(f"Deleted paper trading account {account_id}")
            return True
        
        return False
    
    async def place_order(
        self, 
        account_id: str, 
        order: Order,
        simulate_delay: bool = True
    ) -> str:
        """Place a paper trading order"""
        
        if account_id not in self.accounts:
            raise ValueError(f"Account {account_id} not found")
        
        account = self.accounts[account_id]
        
        # Validate order
        if not await self._validate_order(account, order):
            order.status = OrderStatus.REJECTED
            account.orders[order.id] = order
            raise ValueError("Order validation failed")
        
        # Update market data
        await self._update_market_data(order.symbol)
        
        # Process order based on type
        if order.type == OrderType.MARKET:
            await self._process_market_order(account, order)
        elif order.type == OrderType.LIMIT:
            await self._process_limit_order(account, order)
        elif order.type == OrderType.STOP:
            await self._process_stop_order(account, order)
        else:
            order.status = OrderStatus.REJECTED
            raise ValueError(f"Unsupported order type: {order.type}")
        
        # Store order
        account.orders[order.id] = order
        
        # Simulate processing delay for realism
        if simulate_delay:
            await asyncio.sleep(np.random.uniform(0.1, 0.5))
        
        logger.info(f"Paper order placed: {order.id} - {order.side.value} {order.amount} {order.symbol}")
        return order.id
    
    async def cancel_order(self, account_id: str, order_id: str) -> bool:
        """Cancel a paper trading order"""
        
        if account_id not in self.accounts:
            return False
        
        account = self.accounts[account_id]
        
        if order_id not in account.orders:
            return False
        
        order = account.orders[order_id]
        
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            return False
        
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.utcnow()
        
        logger.info(f"Paper order cancelled: {order_id}")
        return True
    
    async def get_account_status(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get paper trading account status"""
        
        if account_id not in self.accounts:
            return None
        
        account = self.accounts[account_id]
        account.calculate_metrics()
        
        # Calculate current portfolio value
        portfolio_value = account.current_balance
        position_value = 0.0
        
        for symbol, position in account.positions.items():
            try:
                current_price = await self._get_current_price(symbol)
                if current_price:
                    position.current_price = current_price
                    position_value += position.size * current_price
            except:
                continue
        
        total_value = account.current_balance + position_value
        
        return {
            'account_id': account_id,
            'initial_balance': account.initial_balance,
            'current_balance': account.current_balance,
            'portfolio_value': total_value,
            'position_value': position_value,
            'total_pnl': account.total_pnl,
            'total_return_pct': account.total_return_pct,
            'max_drawdown': account.max_drawdown,
            'trades_count': account.trades_count,
            'winning_trades': account.winning_trades,
            'losing_trades': account.losing_trades,
            'win_rate': account.winning_trades / max(1, account.trades_count),
            'open_positions': len(account.positions),
            'open_orders': len([o for o in account.orders.values() if o.is_active]),
            'created_at': account.created_at.isoformat(),
            'commission_rate': account.commission_rate,
            'slippage_rate': account.slippage_rate
        }
    
    async def get_positions(self, account_id: str) -> Dict[str, Position]:
        """Get current positions for account"""
        
        if account_id not in self.accounts:
            return {}
        
        account = self.accounts[account_id]
        
        # Update position values with current prices
        for symbol, position in account.positions.items():
            try:
                current_price = await self._get_current_price(symbol)
                if current_price:
                    position.current_price = current_price
                    
                    if position.side == 'long':
                        position.unrealized_pnl = (current_price - position.entry_price) * position.size
                    else:
                        position.unrealized_pnl = (position.entry_price - current_price) * position.size
            except:
                continue
        
        return account.positions.copy()
    
    async def get_trades(self, account_id: str, limit: int = 100) -> List[Trade]:
        """Get trade history for account"""
        
        if account_id not in self.accounts:
            return []
        
        account = self.accounts[account_id]
        return account.trades[-limit:] if limit else account.trades.copy()
    
    async def get_orders(self, account_id: str, active_only: bool = False) -> List[Order]:
        """Get orders for account"""
        
        if account_id not in self.accounts:
            return []
        
        account = self.accounts[account_id]
        orders = list(account.orders.values())
        
        if active_only:
            orders = [order for order in orders if order.is_active]
        
        return sorted(orders, key=lambda x: x.created_at, reverse=True)
    
    async def run_backtest(
        self,
        account_id: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        strategy_signals: List[Signal],
        initial_balance: float = 100000
    ) -> Dict[str, Any]:
        """Run a backtest simulation"""
        
        # Create temporary account for backtest
        backtest_account_id = await self.create_account(
            initial_balance=initial_balance,
            realistic_fills=False  # Faster execution for backtests
        )
        
        try:
            # Get historical data
            df = await data_manager.fetch_ohlcv(
                symbol=symbol,
                timeframe='1h',
                start_time=start_date,
                end_time=end_date
            )
            
            if df.empty:
                raise ValueError("No historical data available")
            
            # Process signals chronologically
            executed_signals = 0
            
            for signal in sorted(strategy_signals, key=lambda x: x.timestamp):
                # Find corresponding price data
                signal_time = pd.Timestamp(signal.timestamp)
                
                # Find nearest candle
                time_diff = abs(df.index - signal_time)
                nearest_idx = time_diff.argmin()
                
                if time_diff.iloc[nearest_idx] > timedelta(hours=2):
                    continue  # Skip if signal is too far from any candle
                
                candle = df.iloc[nearest_idx]
                
                # Create order from signal
                position_size = self._calculate_backtest_position_size(
                    backtest_account_id, signal, candle['close']
                )
                
                if position_size <= 0:
                    continue
                
                order = Order(
                    id=str(uuid.uuid4()),
                    symbol=signal.symbol,
                    type=OrderType.MARKET,
                    side=OrderSide.BUY if signal.direction == 'buy' else OrderSide.SELL,
                    amount=position_size,
                    price=candle['close']
                )
                
                # Execute order with historical price
                try:
                    await self._execute_backtest_order(
                        backtest_account_id, order, candle, signal
                    )
                    executed_signals += 1
                except Exception as e:
                    logger.warning(f"Failed to execute backtest order: {e}")
                    continue
            
            # Get final results
            final_status = await self.get_account_status(backtest_account_id)
            trades = await self.get_trades(backtest_account_id)
            
            return {
                'backtest_id': backtest_account_id,
                'symbol': symbol,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'initial_balance': initial_balance,
                'final_balance': final_status['current_balance'],
                'total_return': final_status['total_return_pct'],
                'max_drawdown': final_status['max_drawdown'],
                'total_trades': len(trades),
                'signals_processed': len(strategy_signals),
                'signals_executed': executed_signals,
                'win_rate': final_status['win_rate'],
                'trades': [self._trade_to_dict(trade) for trade in trades]
            }
        
        finally:
            # Clean up temporary account
            await self.delete_account(backtest_account_id)
    
    async def _validate_order(self, account: PaperAccount, order: Order) -> bool:
        """Validate order against account constraints"""
        
        # Check balance for buy orders
        if order.side == OrderSide.BUY:
            required_balance = order.amount * (order.price or 0)
            if account.current_balance < required_balance:
                logger.warning(f"Insufficient balance: {account.current_balance} < {required_balance}")
                return False
        
        # Check position for sell orders
        elif order.side == OrderSide.SELL:
            if order.symbol not in account.positions:
                logger.warning(f"No position to sell in {order.symbol}")
                return False
            
            position = account.positions[order.symbol]
            if position.size < order.amount:
                logger.warning(f"Insufficient position size: {position.size} < {order.amount}")
                return False
        
        # Check minimum order size
        min_notional = 10  # $10 minimum
        notional_value = order.amount * (order.price or await self._get_current_price(order.symbol) or 0)
        
        if notional_value < min_notional:
            logger.warning(f"Order below minimum notional: ${notional_value:.2f}")
            return False
        
        return True
    
    async def _process_market_order(self, account: PaperAccount, order: Order):
        """Process a market order"""
        
        current_price = await self._get_current_price(order.symbol)
        if not current_price:
            order.status = OrderStatus.REJECTED
            return
        
        # Apply slippage
        if account.realistic_fills:
            slippage = np.random.normal(0, account.slippage_rate)
            slippage = max(-self.max_slippage, min(self.max_slippage, slippage))
            
            if order.side == OrderSide.BUY:
                fill_price = current_price * (1 + abs(slippage))
            else:
                fill_price = current_price * (1 - abs(slippage))
        else:
            fill_price = current_price
        
        # Execute fill
        order.filled_price = fill_price
        order.filled_amount = order.amount
        order.status = OrderStatus.FILLED
        order.updated_at = datetime.utcnow()
        
        # Calculate commission
        notional_value = order.amount * fill_price
        commission = notional_value * account.commission_rate
        order.commission = commission
        
        # Update account
        await self._update_account_from_fill(account, order)
    
    async def _process_limit_order(self, account: PaperAccount, order: Order):
        """Process a limit order (simplified - immediate check)"""
        
        current_price = await self._get_current_price(order.symbol)
        if not current_price:
            order.status = OrderStatus.REJECTED
            return
        
        # Check if limit order would execute immediately
        should_fill = False
        
        if order.side == OrderSide.BUY and current_price <= order.price:
            should_fill = True
        elif order.side == OrderSide.SELL and current_price >= order.price:
            should_fill = True
        
        if should_fill:
            # Fill at limit price (better execution)
            order.filled_price = order.price
            order.filled_amount = order.amount
            order.status = OrderStatus.FILLED
            order.updated_at = datetime.utcnow()
            
            # Calculate commission
            notional_value = order.amount * order.price
            commission = notional_value * account.commission_rate
            order.commission = commission
            
            # Update account
            await self._update_account_from_fill(account, order)
        else:
            # Order remains open (in real system, would be managed by order book)
            order.status = OrderStatus.OPEN
    
    async def _process_stop_order(self, account: PaperAccount, order: Order):
        """Process a stop order (simplified)"""
        
        current_price = await self._get_current_price(order.symbol)
        if not current_price:
            order.status = OrderStatus.REJECTED
            return
        
        # Check if stop is triggered
        triggered = False
        
        if order.side == OrderSide.BUY and current_price >= order.stop_price:
            triggered = True
        elif order.side == OrderSide.SELL and current_price <= order.stop_price:
            triggered = True
        
        if triggered:
            # Convert to market order
            order.type = OrderType.MARKET
            await self._process_market_order(account, order)
        else:
            order.status = OrderStatus.OPEN
    
    async def _update_account_from_fill(self, account: PaperAccount, order: Order):
        """Update account state after order fill"""
        
        if order.side == OrderSide.BUY:
            # Deduct cash and commission
            total_cost = (order.amount * order.filled_price) + order.commission
            account.current_balance -= total_cost
            
            # Add to position
            if order.symbol in account.positions:
                position = account.positions[order.symbol]
                # Update average price
                total_size = position.size + order.amount
                total_cost_basis = (position.size * position.entry_price) + (order.amount * order.filled_price)
                new_avg_price = total_cost_basis / total_size
                
                position.size = total_size
                position.entry_price = new_avg_price
            else:
                # New position
                account.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    side='long',
                    size=order.amount,
                    entry_price=order.filled_price,
                    current_price=order.filled_price,
                    entry_time=order.updated_at
                )
        
        elif order.side == OrderSide.SELL:
            # Add cash minus commission
            total_proceeds = (order.amount * order.filled_price) - order.commission
            account.current_balance += total_proceeds
            
            # Remove from position
            if order.symbol in account.positions:
                position = account.positions[order.symbol]
                
                # Create trade record
                pnl = (order.filled_price - position.entry_price) * order.amount - order.commission
                
                trade = Trade(
                    id=str(uuid.uuid4()),
                    symbol=order.symbol,
                    side='long',  # Position side
                    entry_price=position.entry_price,
                    exit_price=order.filled_price,
                    size=order.amount,
                    entry_time=position.entry_time,
                    exit_time=order.updated_at,
                    pnl=pnl,
                    pnl_pct=(pnl / (position.entry_price * order.amount)) * 100,
                    commission=order.commission,
                    exit_reason='Manual',
                    strategy='paper_trading'
                )
                
                account.trades.append(trade)
                
                # Update position
                position.size -= order.amount
                if position.size <= 0:
                    del account.positions[order.symbol]
    
    async def _execute_backtest_order(
        self, 
        account_id: str, 
        order: Order, 
        candle: pd.Series,
        signal: Signal
    ):
        """Execute order in backtest mode with historical data"""
        
        account = self.accounts[account_id]
        
        # Use historical prices for realistic fills
        if order.side == OrderSide.BUY:
            # Buy at high of candle (worst case)
            fill_price = candle['high']
        else:
            # Sell at low of candle (worst case)
            fill_price = candle['low']
        
        order.filled_price = fill_price
        order.filled_amount = order.amount
        order.status = OrderStatus.FILLED
        order.updated_at = pd.Timestamp(candle.name).to_pydatetime()
        
        # Calculate commission
        notional_value = order.amount * fill_price
        commission = notional_value * account.commission_rate
        order.commission = commission
        
        # Store order
        account.orders[order.id] = order
        
        # Update account
        await self._update_account_from_fill(account, order)
    
    def _calculate_backtest_position_size(
        self, 
        account_id: str, 
        signal: Signal, 
        price: float
    ) -> float:
        """Calculate position size for backtest"""
        
        account = self.accounts[account_id]
        
        # Use 10% of balance per trade (simplified)
        risk_amount = account.current_balance * 0.1
        
        # Calculate size based on stop loss if available
        if signal.stop_loss:
            risk_per_share = abs(price - signal.stop_loss)
            if risk_per_share > 0:
                return risk_amount / risk_per_share
        
        # Fallback to fixed allocation
        return risk_amount / price
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        
        try:
            # Check cache first
            if symbol in self.price_cache:
                cache_time = self.last_price_update.get(symbol, datetime.min)
                if (datetime.utcnow() - cache_time).total_seconds() < 30:  # 30 second cache
                    return self.price_cache[symbol].get('price')
            
            # Fetch from exchange
            ticker = await self.exchange.get_ticker(symbol)
            price = ticker.get('last', 0)
            
            # Update cache
            self.price_cache[symbol] = {'price': price}
            self.last_price_update[symbol] = datetime.utcnow()
            
            return price
            
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    async def _update_market_data(self, symbol: str):
        """Update market data cache"""
        
        try:
            ticker = await self.exchange.get_ticker(symbol)
            order_book = await self.exchange.get_order_book(symbol, limit=5)
            
            self.price_cache[symbol] = ticker
            self.order_book_cache[symbol] = order_book
            self.last_price_update[symbol] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error updating market data for {symbol}: {e}")
    
    def _trade_to_dict(self, trade: Trade) -> Dict[str, Any]:
        """Convert trade to dictionary"""
        
        return {
            'id': trade.id,
            'symbol': trade.symbol,
            'side': trade.side,
            'entry_price': trade.entry_price,
            'exit_price': trade.exit_price,
            'size': trade.size,
            'entry_time': trade.entry_time.isoformat(),
            'exit_time': trade.exit_time.isoformat(),
            'pnl': trade.pnl,
            'pnl_pct': trade.pnl_pct,
            'commission': trade.commission,
            'exit_reason': trade.exit_reason,
            'duration': str(trade.duration) if hasattr(trade, 'duration') else None
        }
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Get global paper trading statistics"""
        
        total_accounts = len(self.accounts)
        active_accounts = sum(1 for acc in self.accounts.values() if len(acc.positions) > 0)
        
        total_trades = sum(len(acc.trades) for acc in self.accounts.values())
        total_volume = sum(
            sum(trade.size * trade.entry_price for trade in acc.trades)
            for acc in self.accounts.values()
        )
        
        return {
            'total_accounts': total_accounts,
            'active_accounts': active_accounts,
            'total_trades': total_trades,
            'total_volume': total_volume,
            'successful_simulations': self.successful_simulations,
            'avg_trades_per_account': total_trades / max(1, total_accounts)
        }