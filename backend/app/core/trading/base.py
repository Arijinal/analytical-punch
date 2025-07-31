"""
Base classes and interfaces for the Analytical Punch trading bot system.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum
import pandas as pd
import numpy as np


class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order sides"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status"""
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class BotStatus(Enum):
    """Bot status"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class RiskLevel(Enum):
    """Risk levels"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate" 
    AGGRESSIVE = "aggressive"


@dataclass
class Position:
    """Represents a trading position"""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float
    entry_time: datetime
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    @property
    def market_value(self) -> float:
        """Current market value of position"""
        return self.size * self.current_price
    
    @property
    def pnl_pct(self) -> float:
        """PnL percentage"""
        if self.side == 'long':
            return ((self.current_price - self.entry_price) / self.entry_price) * 100
        else:  # short
            return ((self.entry_price - self.current_price) / self.entry_price) * 100


@dataclass
class Order:
    """Represents a trading order"""
    id: str
    symbol: str
    type: OrderType
    side: OrderSide
    amount: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.OPEN
    filled_amount: float = 0.0
    filled_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    commission: float = 0.0
    
    @property
    def remaining_amount(self) -> float:
        """Remaining amount to be filled"""
        return self.amount - self.filled_amount
    
    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.status == OrderStatus.FILLED
    
    @property
    def is_active(self) -> bool:
        """Check if order is active"""
        return self.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]


@dataclass
class Trade:
    """Represents a completed trade"""
    id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    commission: float
    exit_reason: str
    strategy: str
    
    @property
    def duration(self) -> timedelta:
        """Trade duration"""
        return self.exit_time - self.entry_time
    
    @property
    def was_profitable(self) -> bool:
        """Check if trade was profitable"""
        return self.pnl > 0


@dataclass
class Signal:
    """Trading signal"""
    id: str
    symbol: str
    direction: str  # 'buy', 'sell', 'hold'
    confidence: float
    price: float
    timestamp: datetime
    strategy: str
    indicators: Dict[str, Any]
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    
    @property
    def is_strong(self) -> bool:
        """Check if signal is strong enough to act on"""
        return self.confidence >= 0.7


@dataclass
class Portfolio:
    """Portfolio state"""
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    orders: Dict[str, Order] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    total_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol"""
        return self.positions.get(symbol)
    
    def has_position(self, symbol: str) -> bool:
        """Check if we have a position in symbol"""
        return symbol in self.positions
    
    def update_portfolio_value(self, current_prices: Dict[str, float]):
        """Update portfolio value with current prices"""
        position_value = 0.0
        unrealized_pnl = 0.0
        
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                position.current_price = current_prices[symbol]
                position_value += position.market_value
                
                if position.side == 'long':
                    position.unrealized_pnl = (position.current_price - position.entry_price) * position.size
                else:  # short
                    position.unrealized_pnl = (position.entry_price - position.current_price) * position.size
                
                unrealized_pnl += position.unrealized_pnl
        
        self.total_value = self.cash + position_value
        self.unrealized_pnl = unrealized_pnl


class ExchangeInterface(ABC):
    """Abstract interface for exchange connections"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to exchange"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from exchange"""
        pass
    
    @abstractmethod
    async def get_balance(self) -> Dict[str, float]:
        """Get account balance"""
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> str:
        """Place an order"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Order:
        """Get order status"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> Dict[str, Position]:
        """Get current positions"""
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get ticker data"""
        pass


class RiskManager(ABC):
    """Abstract risk management interface"""
    
    @abstractmethod
    def validate_order(self, order: Order, portfolio: Portfolio) -> bool:
        """Validate if order passes risk checks"""
        pass
    
    @abstractmethod
    def calculate_position_size(
        self, 
        signal: Signal, 
        portfolio: Portfolio, 
        risk_per_trade: float
    ) -> float:
        """Calculate position size based on risk"""
        pass
    
    @abstractmethod
    def check_portfolio_risk(self, portfolio: Portfolio) -> Dict[str, Any]:
        """Check overall portfolio risk"""
        pass


class TradingStrategy(ABC):
    """Abstract trading strategy interface"""
    
    def __init__(self, name: str, parameters: Dict[str, Any]):
        self.name = name
        self.parameters = parameters
        self.active = False
    
    @abstractmethod
    async def generate_signals(
        self, 
        symbol: str, 
        df: pd.DataFrame, 
        indicators: Dict[str, Any]
    ) -> List[Signal]:
        """Generate trading signals"""
        pass
    
    @abstractmethod
    def get_required_indicators(self) -> List[str]:
        """Get list of required indicators"""
        pass
    
    @abstractmethod
    def validate_parameters(self) -> bool:
        """Validate strategy parameters"""
        pass


class TradingBot(ABC):
    """Abstract trading bot base class"""
    
    def __init__(
        self,
        bot_id: str,
        name: str,
        exchange: ExchangeInterface,
        risk_manager: RiskManager,
        strategies: List[TradingStrategy],
        config: Dict[str, Any]
    ):
        self.bot_id = bot_id
        self.name = name
        self.exchange = exchange
        self.risk_manager = risk_manager
        self.strategies = strategies
        self.config = config
        
        self.status = BotStatus.STOPPED
        self.portfolio = Portfolio(cash=config.get('initial_capital', 10000))
        self.running = False
        self.paper_trading = config.get('paper_trading', True)
        
        # Performance tracking
        self.trades_today = 0
        self.total_trades = 0
        self.win_rate = 0.0
        self.profit_factor = 0.0
        self.max_drawdown = 0.0
        
        # Event handlers
        self.on_signal_handlers: List[Callable] = []
        self.on_trade_handlers: List[Callable] = []
        self.on_error_handlers: List[Callable] = []
    
    @abstractmethod
    async def start(self):
        """Start the trading bot"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the trading bot"""
        pass
    
    @abstractmethod
    async def pause(self):
        """Pause the trading bot"""
        pass
    
    @abstractmethod
    async def resume(self):
        """Resume the trading bot"""
        pass
    
    def add_signal_handler(self, handler: Callable):
        """Add signal event handler"""
        self.on_signal_handlers.append(handler)
    
    def add_trade_handler(self, handler: Callable):
        """Add trade event handler"""
        self.on_trade_handlers.append(handler)
    
    def add_error_handler(self, handler: Callable):
        """Add error event handler"""
        self.on_error_handlers.append(handler)
    
    async def _emit_signal(self, signal: Signal):
        """Emit signal event"""
        for handler in self.on_signal_handlers:
            try:
                await handler(signal)
            except Exception as e:
                await self._emit_error(f"Signal handler error: {e}")
    
    async def _emit_trade(self, trade: Trade):
        """Emit trade event"""
        for handler in self.on_trade_handlers:
            try:
                await handler(trade)
            except Exception as e:
                await self._emit_error(f"Trade handler error: {e}")
    
    async def _emit_error(self, error: str):
        """Emit error event"""
        for handler in self.on_error_handlers:
            try:
                await handler(error)
            except Exception:
                pass  # Avoid infinite error loops
    
    def get_status(self) -> Dict[str, Any]:
        """Get bot status"""
        return {
            'bot_id': self.bot_id,
            'name': self.name,
            'status': self.status.value,
            'paper_trading': self.paper_trading,
            'portfolio_value': self.portfolio.total_value,
            'cash': self.portfolio.cash,
            'positions': len(self.portfolio.positions),
            'trades_today': self.trades_today,
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'max_drawdown': self.max_drawdown
        }


class MultiStrategyBot(TradingBot):
    """Bot that manages multiple strategies with allocation"""
    
    def __init__(
        self,
        bot_id: str,
        name: str,
        exchange: ExchangeInterface,
        risk_manager: RiskManager,
        strategies: List[TradingStrategy],
        strategy_allocations: Dict[str, float],
        config: Dict[str, Any]
    ):
        super().__init__(bot_id, name, exchange, risk_manager, strategies, config)
        self.strategy_allocations = strategy_allocations
        self.strategy_performance = {s.name: {'trades': 0, 'pnl': 0.0} for s in strategies}
    
    def rebalance_allocations(self):
        """Dynamically rebalance strategy allocations based on performance"""
        total_pnl = sum(perf['pnl'] for perf in self.strategy_performance.values())
        
        if total_pnl > 0:
            # Increase allocation to profitable strategies
            for strategy_name, perf in self.strategy_performance.items():
                if perf['pnl'] > 0 and perf['trades'] > 5:
                    current_alloc = self.strategy_allocations.get(strategy_name, 0)
                    # Increase by up to 10% based on relative performance
                    performance_ratio = perf['pnl'] / total_pnl
                    new_alloc = min(current_alloc * (1 + performance_ratio * 0.1), 0.5)
                    self.strategy_allocations[strategy_name] = new_alloc
        
        # Normalize allocations to sum to 1.0
        total_alloc = sum(self.strategy_allocations.values())
        if total_alloc > 0:
            for strategy_name in self.strategy_allocations:
                self.strategy_allocations[strategy_name] /= total_alloc