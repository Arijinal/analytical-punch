"""
Database models for trading bot system.
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, JSON,
    ForeignKey, Enum as SQLEnum, UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum
import uuid

Base = declarative_base()


class BotStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class OrderStatus(Enum):
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class TradingBot(Base):
    """Trading bot configuration and state"""
    __tablename__ = 'trading_bots'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # Configuration
    config = Column(JSON, nullable=False)
    strategies = Column(JSON, nullable=False)  # Strategy configurations
    symbols = Column(JSON, nullable=False)     # List of symbols to trade
    timeframes = Column(JSON, nullable=False)  # List of timeframes
    
    # State
    status = Column(SQLEnum(BotStatus), default=BotStatus.STOPPED)
    paper_trading = Column(Boolean, default=True)
    
    # Performance
    initial_capital = Column(Float, default=0.0)
    current_capital = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)
    total_return_pct = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    started_at = Column(DateTime)
    stopped_at = Column(DateTime)
    
    # Risk management
    max_position_size = Column(Float, default=0.1)
    max_daily_loss = Column(Float, default=0.05)
    max_drawdown_limit = Column(Float, default=0.15)
    
    # Relationships
    orders = relationship("Order", back_populates="bot", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="bot", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="bot", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="bot", cascade="all, delete-orphan")
    alerts = relationship("SafetyAlert", back_populates="bot", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_bot_status', 'status'),
        Index('idx_bot_created', 'created_at'),
    )


class Position(Base):
    """Current trading positions"""
    __tablename__ = 'positions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bot_id = Column(String(36), ForeignKey('trading_bots.id'), nullable=False)
    
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # 'long' or 'short'
    size = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    
    # P&L
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)
    
    # Risk management
    stop_loss = Column(Float)
    take_profit = Column(Float)
    
    # Timestamps
    entry_time = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Strategy info
    strategy = Column(String(50))
    entry_signal_id = Column(String(36))
    
    # Relationships
    bot = relationship("TradingBot", back_populates="positions")
    
    __table_args__ = (
        Index('idx_position_bot_symbol', 'bot_id', 'symbol'),
        Index('idx_position_entry_time', 'entry_time'),
    )


class Order(Base):
    """Trading orders"""
    __tablename__ = 'orders'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bot_id = Column(String(36), ForeignKey('trading_bots.id'), nullable=False)
    
    symbol = Column(String(20), nullable=False)
    type = Column(SQLEnum(OrderType), nullable=False)
    side = Column(SQLEnum(OrderSide), nullable=False)
    amount = Column(Float, nullable=False)
    price = Column(Float)
    stop_price = Column(Float)
    
    # Execution
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.OPEN)
    filled_amount = Column(Float, default=0.0)
    filled_price = Column(Float)
    commission = Column(Float, default=0.0)
    
    # Exchange info
    exchange_order_id = Column(String(100))
    exchange = Column(String(20), default='binance')
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    filled_at = Column(DateTime)
    
    # Strategy info
    strategy = Column(String(50))
    signal_id = Column(String(36))
    
    # Relationships
    bot = relationship("TradingBot", back_populates="orders")
    
    __table_args__ = (
        Index('idx_order_bot_status', 'bot_id', 'status'),
        Index('idx_order_symbol_time', 'symbol', 'created_at'),
        Index('idx_order_exchange_id', 'exchange_order_id'),
    )


class Trade(Base):
    """Completed trades"""
    __tablename__ = 'trades'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bot_id = Column(String(36), ForeignKey('trading_bots.id'), nullable=False)
    
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # 'long' or 'short'
    
    # Entry
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    entry_order_id = Column(String(36))
    
    # Exit
    exit_price = Column(Float, nullable=False)
    exit_time = Column(DateTime, nullable=False)
    exit_order_id = Column(String(36))
    exit_reason = Column(String(50))  # 'take_profit', 'stop_loss', 'manual', etc.
    
    # Size and P&L
    size = Column(Float, nullable=False)
    pnl = Column(Float, nullable=False)
    pnl_pct = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)
    
    # Duration
    duration_seconds = Column(Integer)
    
    # Strategy info
    strategy = Column(String(50), nullable=False)
    entry_signal_id = Column(String(36))
    confidence = Column(Float)
    
    # Risk metrics
    risk_reward_ratio = Column(Float)
    max_adverse_excursion = Column(Float)  # MAE
    max_favorable_excursion = Column(Float)  # MFE
    
    # Relationships
    bot = relationship("TradingBot", back_populates="trades")
    
    __table_args__ = (
        Index('idx_trade_bot_time', 'bot_id', 'exit_time'),
        Index('idx_trade_symbol_time', 'symbol', 'exit_time'),
        Index('idx_trade_strategy', 'strategy'),
        Index('idx_trade_pnl', 'pnl'),
    )


class Signal(Base):
    """Trading signals generated by strategies"""
    __tablename__ = 'signals'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bot_id = Column(String(36), ForeignKey('trading_bots.id'), nullable=False)
    
    symbol = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=False)  # 'buy', 'sell', 'hold'
    confidence = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    
    # Strategy info
    strategy = Column(String(50), nullable=False)
    timeframe = Column(String(10), nullable=False)
    
    # Risk management
    stop_loss = Column(Float)
    take_profit = Column(Float)
    risk_reward_ratio = Column(Float)
    
    # Signal data
    indicators = Column(JSON)  # Indicator values that generated the signal
    conditions = Column(JSON)  # Conditions that were met
    
    # Status
    executed = Column(Boolean, default=False)
    execution_price = Column(Float)
    execution_time = Column(DateTime)
    order_id = Column(String(36))
    
    # Timestamps
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    bot = relationship("TradingBot", back_populates="signals")
    
    __table_args__ = (
        Index('idx_signal_bot_time', 'bot_id', 'timestamp'),
        Index('idx_signal_strategy_symbol', 'strategy', 'symbol'),
        Index('idx_signal_executed', 'executed'),
    )


class SafetyAlert(Base):
    """Safety alerts and interventions"""
    __tablename__ = 'safety_alerts'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bot_id = Column(String(36), ForeignKey('trading_bots.id'))  # NULL for global alerts
    
    level = Column(SQLEnum(AlertLevel), nullable=False)
    trigger_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    
    # Alert data
    data = Column(JSON)
    actions_taken = Column(JSON)
    
    # Status
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(100))
    acknowledged_at = Column(DateTime)
    
    # Timestamps
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    bot = relationship("TradingBot", back_populates="alerts")
    
    __table_args__ = (
        Index('idx_alert_level_time', 'level', 'timestamp'),
        Index('idx_alert_bot_acknowledged', 'bot_id', 'acknowledged'),
        Index('idx_alert_trigger_type', 'trigger_type'),
    )


class StrategyPerformance(Base):
    """Strategy performance metrics"""
    __tablename__ = 'strategy_performance'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bot_id = Column(String(36), ForeignKey('trading_bots.id'), nullable=False)
    
    strategy_name = Column(String(50), nullable=False)
    
    # Performance metrics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    total_pnl = Column(Float, default=0.0)
    avg_win = Column(Float, default=0.0)
    avg_loss = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    
    max_drawdown = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    
    # Signal metrics
    signals_generated = Column(Integer, default=0)
    signals_executed = Column(Integer, default=0)
    execution_rate = Column(Float, default=0.0)
    avg_confidence = Column(Float, default=0.0)
    
    # Allocation
    current_allocation = Column(Float, default=0.0)
    allocated_capital = Column(Float, default=0.0)
    
    # Timestamps
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_strategy_perf_bot_name', 'bot_id', 'strategy_name'),
        Index('idx_strategy_perf_period', 'period_start', 'period_end'),
        UniqueConstraint('bot_id', 'strategy_name', 'period_start', name='uq_strategy_period'),
    )


class ExecutionReport(Base):
    """Order execution reports"""
    __tablename__ = 'execution_reports'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey('orders.id'), nullable=False)
    bot_id = Column(String(36), ForeignKey('trading_bots.id'), nullable=False)
    
    symbol = Column(String(20), nullable=False)
    requested_amount = Column(Float, nullable=False)
    executed_amount = Column(Float, nullable=False)
    
    # Pricing
    requested_price = Column(Float)
    average_price = Column(Float, nullable=False)
    total_slippage = Column(Float, default=0.0)
    fees_paid = Column(Float, default=0.0)
    
    # Execution details
    strategy_used = Column(String(20), nullable=False)  # IMMEDIATE, TWAP, VWAP, ICEBERG
    chunks_executed = Column(Integer, default=1)
    execution_time = Column(Float, default=0.0)  # seconds
    
    # Market impact
    market_impact = Column(Float, default=0.0)
    price_improvement = Column(Float, default=0.0)
    
    # Status
    success = Column(Boolean, nullable=False)
    error_message = Column(Text)
    
    # Timestamps
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_execution_bot_time', 'bot_id', 'started_at'),
        Index('idx_execution_symbol', 'symbol'),
        Index('idx_execution_strategy', 'strategy_used'),
    )


class PaperTradingAccount(Base):
    """Paper trading accounts"""
    __tablename__ = 'paper_accounts'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bot_id = Column(String(36), ForeignKey('trading_bots.id'))  # NULL for standalone accounts
    
    name = Column(String(100), nullable=False)
    initial_balance = Column(Float, nullable=False)
    current_balance = Column(Float, nullable=False)
    
    # Performance
    total_pnl = Column(Float, default=0.0)
    total_return_pct = Column(Float, default=0.0)
    max_balance = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    
    # Trading stats
    trades_count = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    # Settings
    commission_rate = Column(Float, default=0.001)
    slippage_rate = Column(Float, default=0.0005)
    realistic_fills = Column(Boolean, default=True)
    
    # Status
    active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_activity = Column(DateTime)
    
    __table_args__ = (
        Index('idx_paper_account_bot', 'bot_id'),
        Index('idx_paper_account_active', 'active'),
    )


class MarketData(Base):
    """Market data cache"""
    __tablename__ = 'market_data'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    
    # OHLCV data
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    # Additional data
    bid = Column(Float)
    ask = Column(Float)
    spread = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_market_data_symbol_time', 'symbol', 'timeframe', 'timestamp'),
        UniqueConstraint('symbol', 'timeframe', 'timestamp', name='uq_market_data'),
    )


class SystemLog(Base):
    """System logs and events"""
    __tablename__ = 'system_logs'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    level = Column(String(10), nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    component = Column(String(50), nullable=False)  # bot, exchange, risk, etc.
    event = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    
    # Context
    bot_id = Column(String(36))
    symbol = Column(String(20))
    strategy = Column(String(50))
    data = Column(JSON)
    
    # Timestamps
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_log_level_time', 'level', 'timestamp'),
        Index('idx_log_component_time', 'component', 'timestamp'),
        Index('idx_log_bot', 'bot_id'),
    )