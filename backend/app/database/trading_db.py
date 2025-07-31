"""
Database management for trading bot system.
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
import os
import logging

from app.config import get_config
from app.models.trading import (
    Base, TradingBot, Position, Order, Trade, Signal, SafetyAlert,
    StrategyPerformance, ExecutionReport, PaperTradingAccount,
    MarketData, SystemLog
)

config = get_config()
logger = logging.getLogger(__name__)


class TradingDatabase:
    """Database manager for trading bot system"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or config.DATABASE_URL
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
    
    def initialize(self):
        """Initialize database connection and create tables"""
        if self._initialized:
            return
        
        try:
            # Create engine
            if self.database_url.startswith('sqlite'):
                # SQLite configuration
                self.engine = create_engine(
                    self.database_url,
                    poolclass=StaticPool,
                    connect_args={
                        "check_same_thread": False,
                        "timeout": 20
                    },
                    echo=config.DEBUG
                )
            else:
                # PostgreSQL configuration
                self.engine = create_engine(
                    self.database_url,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    echo=config.DEBUG
                )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # Create all tables
            Base.metadata.create_all(bind=self.engine)
            
            self._initialized = True
            logger.info("Trading database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize trading database: {e}")
            raise
    
    @contextmanager
    def get_session(self):
        """Get database session with automatic cleanup"""
        if not self._initialized:
            self.initialize()
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_session_sync(self) -> Session:
        """Get database session (manual management)"""
        if not self._initialized:
            self.initialize()
        
        return self.SessionLocal()
    
    def close(self):
        """Close database connections"""
        if self.engine:
            self.engine.dispose()
            logger.info("Trading database connections closed")


# Global database instance
trading_db = TradingDatabase()


class TradingBotRepository:
    """Repository for trading bot operations"""
    
    def __init__(self, db: TradingDatabase = None):
        self.db = db or trading_db
    
    def create_bot(self, bot_data: Dict[str, Any]) -> TradingBot:
        """Create a new trading bot"""
        with self.db.get_session() as session:
            bot = TradingBot(**bot_data)
            session.add(bot)
            session.flush()
            session.refresh(bot)
            return bot
    
    def get_bot(self, bot_id: str) -> Optional[TradingBot]:
        """Get trading bot by ID"""
        with self.db.get_session() as session:
            return session.query(TradingBot).filter(TradingBot.id == bot_id).first()
    
    def get_all_bots(self, active_only: bool = False) -> List[TradingBot]:
        """Get all trading bots"""
        with self.db.get_session() as session:
            query = session.query(TradingBot)
            if active_only:
                from app.models.trading import BotStatus
                query = query.filter(TradingBot.status.in_([BotStatus.RUNNING, BotStatus.PAUSED]))
            return query.all()
    
    def update_bot(self, bot_id: str, updates: Dict[str, Any]) -> bool:
        """Update trading bot"""
        with self.db.get_session() as session:
            result = session.query(TradingBot).filter(TradingBot.id == bot_id).update(updates)
            return result > 0
    
    def delete_bot(self, bot_id: str) -> bool:
        """Delete trading bot"""
        with self.db.get_session() as session:
            result = session.query(TradingBot).filter(TradingBot.id == bot_id).delete()
            return result > 0
    
    def get_bot_performance(self, bot_id: str) -> Dict[str, Any]:
        """Get bot performance metrics"""
        with self.db.get_session() as session:
            bot = session.query(TradingBot).filter(TradingBot.id == bot_id).first()
            if not bot:
                return {}
            
            # Get recent trades
            recent_trades = session.query(Trade).filter(
                Trade.bot_id == bot_id
            ).order_by(Trade.exit_time.desc()).limit(100).all()
            
            # Calculate additional metrics
            if recent_trades:
                total_pnl = sum(trade.pnl for trade in recent_trades)
                win_count = sum(1 for trade in recent_trades if trade.pnl > 0)
                win_rate = win_count / len(recent_trades)
                
                if win_count > 0 and len(recent_trades) > win_count:
                    avg_win = sum(trade.pnl for trade in recent_trades if trade.pnl > 0) / win_count
                    avg_loss = sum(trade.pnl for trade in recent_trades if trade.pnl < 0) / (len(recent_trades) - win_count)
                    profit_factor = abs(avg_win * win_count) / abs(avg_loss * (len(recent_trades) - win_count)) if avg_loss < 0 else float('inf')
                else:
                    avg_win = avg_loss = profit_factor = 0
            else:
                total_pnl = win_rate = avg_win = avg_loss = profit_factor = 0
            
            return {
                'bot_id': bot_id,
                'name': bot.name,
                'status': bot.status.value,
                'initial_capital': bot.initial_capital,
                'current_capital': bot.current_capital,
                'total_pnl': total_pnl,
                'total_return_pct': bot.total_return_pct,
                'max_drawdown': bot.max_drawdown,
                'total_trades': len(recent_trades),
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'created_at': bot.created_at,
                'started_at': bot.started_at,
                'stopped_at': bot.stopped_at
            }


class OrderRepository:
    """Repository for order operations"""
    
    def __init__(self, db: TradingDatabase = None):
        self.db = db or trading_db
    
    def create_order(self, order_data: Dict[str, Any]) -> Order:
        """Create a new order"""
        with self.db.get_session() as session:
            order = Order(**order_data)
            session.add(order)
            session.flush()
            session.refresh(order)
            return order
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        with self.db.get_session() as session:
            return session.query(Order).filter(Order.id == order_id).first()
    
    def get_bot_orders(
        self, 
        bot_id: str, 
        active_only: bool = False,
        limit: int = 100
    ) -> List[Order]:
        """Get orders for a bot"""
        with self.db.get_session() as session:
            query = session.query(Order).filter(Order.bot_id == bot_id)
            
            if active_only:
                from app.models.trading import OrderStatus
                query = query.filter(Order.status.in_([
                    OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED
                ]))
            
            return query.order_by(Order.created_at.desc()).limit(limit).all()
    
    def update_order(self, order_id: str, updates: Dict[str, Any]) -> bool:
        """Update order"""
        with self.db.get_session() as session:
            result = session.query(Order).filter(Order.id == order_id).update(updates)
            return result > 0
    
    def get_orders_by_status(self, status: str, limit: int = 100) -> List[Order]:
        """Get orders by status"""
        with self.db.get_session() as session:
            from app.models.trading import OrderStatus
            return session.query(Order).filter(
                Order.status == OrderStatus(status)
            ).order_by(Order.created_at.desc()).limit(limit).all()


class TradeRepository:
    """Repository for trade operations"""
    
    def __init__(self, db: TradingDatabase = None):
        self.db = db or trading_db
    
    def create_trade(self, trade_data: Dict[str, Any]) -> Trade:
        """Create a new trade"""
        with self.db.get_session() as session:
            trade = Trade(**trade_data)
            session.add(trade)
            session.flush()
            session.refresh(trade)
            return trade
    
    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID"""
        with self.db.get_session() as session:
            return session.query(Trade).filter(Trade.id == trade_id).first()
    
    def get_bot_trades(
        self, 
        bot_id: str, 
        limit: int = 100,
        strategy: Optional[str] = None
    ) -> List[Trade]:
        """Get trades for a bot"""
        with self.db.get_session() as session:
            query = session.query(Trade).filter(Trade.bot_id == bot_id)
            
            if strategy:
                query = query.filter(Trade.strategy == strategy)
            
            return query.order_by(Trade.exit_time.desc()).limit(limit).all()
    
    def get_strategy_performance(
        self, 
        bot_id: str, 
        strategy: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get strategy performance metrics"""
        with self.db.get_session() as session:
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            trades = session.query(Trade).filter(
                Trade.bot_id == bot_id,
                Trade.strategy == strategy,
                Trade.exit_time >= cutoff_date
            ).all()
            
            if not trades:
                return {}
            
            # Calculate metrics
            total_trades = len(trades)
            winning_trades = sum(1 for trade in trades if trade.pnl > 0)
            losing_trades = total_trades - winning_trades
            
            total_pnl = sum(trade.pnl for trade in trades)
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            if winning_trades > 0:
                avg_win = sum(trade.pnl for trade in trades if trade.pnl > 0) / winning_trades
            else:
                avg_win = 0
            
            if losing_trades > 0:
                avg_loss = sum(trade.pnl for trade in trades if trade.pnl < 0) / losing_trades
            else:
                avg_loss = 0
            
            if avg_loss < 0 and avg_win > 0:
                profit_factor = abs(avg_win * winning_trades) / abs(avg_loss * losing_trades)
            else:
                profit_factor = 0
            
            return {
                'strategy': strategy,
                'period_days': days,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'avg_trade_duration': sum(
                    trade.duration_seconds for trade in trades if trade.duration_seconds
                ) / len([t for t in trades if t.duration_seconds]) if trades else 0
            }


class PositionRepository:
    """Repository for position operations"""
    
    def __init__(self, db: TradingDatabase = None):
        self.db = db or trading_db
    
    def create_position(self, position_data: Dict[str, Any]) -> Position:
        """Create a new position"""
        with self.db.get_session() as session:
            position = Position(**position_data)
            session.add(position)
            session.flush()
            session.refresh(position)
            return position
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID"""
        with self.db.get_session() as session:
            return session.query(Position).filter(Position.id == position_id).first()
    
    def get_bot_positions(self, bot_id: str) -> List[Position]:
        """Get all positions for a bot"""
        with self.db.get_session() as session:
            return session.query(Position).filter(Position.bot_id == bot_id).all()
    
    def get_position_by_symbol(self, bot_id: str, symbol: str) -> Optional[Position]:
        """Get position by bot and symbol"""
        with self.db.get_session() as session:
            return session.query(Position).filter(
                Position.bot_id == bot_id,
                Position.symbol == symbol
            ).first()
    
    def update_position(self, position_id: str, updates: Dict[str, Any]) -> bool:
        """Update position"""
        with self.db.get_session() as session:
            result = session.query(Position).filter(Position.id == position_id).update(updates)
            return result > 0
    
    def delete_position(self, position_id: str) -> bool:
        """Delete position"""
        with self.db.get_session() as session:
            result = session.query(Position).filter(Position.id == position_id).delete()
            return result > 0


class AlertRepository:
    """Repository for safety alert operations"""
    
    def __init__(self, db: TradingDatabase = None):
        self.db = db or trading_db
    
    def create_alert(self, alert_data: Dict[str, Any]) -> SafetyAlert:
        """Create a new alert"""
        with self.db.get_session() as session:
            alert = SafetyAlert(**alert_data)
            session.add(alert)
            session.flush()
            session.refresh(alert)
            return alert
    
    def get_alerts(
        self, 
        bot_id: Optional[str] = None,
        level: Optional[str] = None,
        unacknowledged_only: bool = False,
        limit: int = 100
    ) -> List[SafetyAlert]:
        """Get alerts with filters"""
        with self.db.get_session() as session:
            query = session.query(SafetyAlert)
            
            if bot_id:
                query = query.filter(SafetyAlert.bot_id == bot_id)
            
            if level:
                from app.models.trading import AlertLevel
                query = query.filter(SafetyAlert.level == AlertLevel(level))
            
            if unacknowledged_only:
                query = query.filter(SafetyAlert.acknowledged == False)
            
            return query.order_by(SafetyAlert.timestamp.desc()).limit(limit).all()
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        with self.db.get_session() as session:
            from datetime import datetime
            result = session.query(SafetyAlert).filter(SafetyAlert.id == alert_id).update({
                'acknowledged': True,
                'acknowledged_by': acknowledged_by,
                'acknowledged_at': datetime.utcnow()
            })
            return result > 0


class SystemLogRepository:
    """Repository for system log operations"""
    
    def __init__(self, db: TradingDatabase = None):
        self.db = db or trading_db
    
    def log_event(
        self,
        level: str,
        component: str,
        event: str,
        message: str,
        bot_id: Optional[str] = None,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> SystemLog:
        """Log a system event"""
        with self.db.get_session() as session:
            from datetime import datetime
            
            log_entry = SystemLog(
                level=level,
                component=component,
                event=event,
                message=message,
                bot_id=bot_id,
                symbol=symbol,
                strategy=strategy,
                data=data,
                timestamp=datetime.utcnow()
            )
            
            session.add(log_entry)
            session.flush()
            session.refresh(log_entry)
            return log_entry
    
    def get_logs(
        self,
        level: Optional[str] = None,
        component: Optional[str] = None,
        bot_id: Optional[str] = None,
        limit: int = 1000
    ) -> List[SystemLog]:
        """Get system logs with filters"""
        with self.db.get_session() as session:
            query = session.query(SystemLog)
            
            if level:
                query = query.filter(SystemLog.level == level)
            
            if component:
                query = query.filter(SystemLog.component == component)
            
            if bot_id:
                query = query.filter(SystemLog.bot_id == bot_id)
            
            return query.order_by(SystemLog.timestamp.desc()).limit(limit).all()


# Repository instances
bot_repository = TradingBotRepository()
order_repository = OrderRepository()
trade_repository = TradeRepository()
position_repository = PositionRepository()
alert_repository = AlertRepository()
log_repository = SystemLogRepository()


def initialize_trading_database():
    """Initialize the trading database"""
    trading_db.initialize()


def get_trading_session():
    """Get a trading database session"""
    return trading_db.get_session()


def close_trading_database():
    """Close trading database connections"""
    trading_db.close()