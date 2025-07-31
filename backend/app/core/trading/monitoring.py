"""
Real-time monitoring system with alerts for trading bots.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from app.core.trading.base import TradingBot, Portfolio, Trade, Position
from app.core.trading.safety import SafetyManager, SafetyAlert, AlertLevel
from app.database.trading_db import log_repository, alert_repository
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class MonitoringEvent(Enum):
    """Monitoring event types"""
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    BOT_PAUSED = "bot_paused"
    BOT_RESUMED = "bot_resumed"
    BOT_ERROR = "bot_error"
    
    TRADE_OPENED = "trade_opened"
    TRADE_CLOSED = "trade_closed"
    POSITION_UPDATED = "position_updated"
    
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_EXECUTED = "signal_executed"
    
    ALERT_TRIGGERED = "alert_triggered"
    KILL_SWITCH_ACTIVATED = "kill_switch_activated"
    
    PERFORMANCE_UPDATE = "performance_update"
    PORTFOLIO_UPDATE = "portfolio_update"
    
    MARKET_DATA_UPDATE = "market_data_update"
    CONNECTIVITY_ISSUE = "connectivity_issue"


@dataclass
class MonitoringAlert:
    """Real-time monitoring alert"""
    id: str
    event_type: MonitoringEvent
    level: AlertLevel
    bot_id: Optional[str]
    title: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'event_type': self.event_type.value,
            'level': self.level.value,
            'bot_id': self.bot_id,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'acknowledged': self.acknowledged
        }


@dataclass
class PerformanceMetrics:
    """Real-time performance metrics"""
    bot_id: str
    timestamp: datetime
    portfolio_value: float
    total_pnl: float
    daily_pnl: float
    unrealized_pnl: float
    drawdown: float
    win_rate: float
    total_trades: int
    active_positions: int
    strategy_allocations: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'bot_id': self.bot_id,
            'timestamp': self.timestamp.isoformat(),
            'portfolio_value': self.portfolio_value,
            'total_pnl': self.total_pnl,
            'daily_pnl': self.daily_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'drawdown': self.drawdown,
            'win_rate': self.win_rate,
            'total_trades': self.total_trades,
            'active_positions': self.active_positions,
            'strategy_allocations': self.strategy_allocations
        }


class AlertManager:
    """Manages real-time alerts and notifications"""
    
    def __init__(self):
        self.alert_handlers: List[Callable] = []
        self.active_alerts: Dict[str, MonitoringAlert] = {}
        self.alert_history: List[MonitoringAlert] = []
        self.max_history = 1000
        
        # Alert rules
        self.alert_rules = {
            'high_drawdown': {
                'threshold': 0.1,  # 10%
                'level': AlertLevel.WARNING,
                'cooldown': 3600  # 1 hour
            },
            'large_loss': {
                'threshold': 0.05,  # 5% single trade loss
                'level': AlertLevel.WARNING,
                'cooldown': 300  # 5 minutes
            },
            'consecutive_losses': {
                'threshold': 3,
                'level': AlertLevel.WARNING,
                'cooldown': 1800  # 30 minutes
            },
            'connectivity_issues': {
                'threshold': 3,  # 3 failed connections
                'level': AlertLevel.CRITICAL,
                'cooldown': 600  # 10 minutes
            }
        }
        
        self.last_triggered: Dict[str, datetime] = {}
    
    def add_alert_handler(self, handler: Callable):
        """Add alert handler"""
        self.alert_handlers.append(handler)
    
    async def trigger_alert(
        self,
        event_type: MonitoringEvent,
        level: AlertLevel,
        title: str,
        message: str,
        bot_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Trigger a new alert"""
        
        alert = MonitoringAlert(
            id=str(uuid.uuid4()),
            event_type=event_type,
            level=level,
            bot_id=bot_id,
            title=title,
            message=message,
            data=data or {}
        )
        
        # Store alert
        self.active_alerts[alert.id] = alert
        self.alert_history.append(alert)
        
        # Trim history if needed
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        
        # Store in database for persistence
        try:
            alert_repository.create_alert({
                'bot_id': bot_id,
                'level': level,
                'trigger_type': event_type.value,
                'message': message,
                'data': data,
                'timestamp': alert.timestamp
            })
        except Exception as e:
            logger.error(f"Error storing alert in database: {e}")
        
        # Notify handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")
        
        logger.info(f"Alert triggered: {title} - {message}")
        return alert.id
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            return True
        return False
    
    def get_active_alerts(self, bot_id: Optional[str] = None) -> List[MonitoringAlert]:
        """Get active alerts"""
        alerts = list(self.active_alerts.values())
        
        if bot_id:
            alerts = [alert for alert in alerts if alert.bot_id == bot_id]
        
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)
    
    def get_alert_history(
        self, 
        limit: int = 100,
        level: Optional[AlertLevel] = None
    ) -> List[MonitoringAlert]:
        """Get alert history"""
        alerts = self.alert_history
        
        if level:
            alerts = [alert for alert in alerts if alert.level == level]
        
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def check_alert_rules(self, bot_id: str, metrics: PerformanceMetrics):
        """Check if any alert rules are triggered"""
        current_time = datetime.utcnow()
        
        # High drawdown alert
        if metrics.drawdown > self.alert_rules['high_drawdown']['threshold']:
            rule_key = f"high_drawdown_{bot_id}"
            if self._can_trigger_rule(rule_key, current_time):
                asyncio.create_task(self.trigger_alert(
                    MonitoringEvent.ALERT_TRIGGERED,
                    AlertLevel.WARNING,
                    "High Drawdown Alert",
                    f"Drawdown reached {metrics.drawdown:.2%}",
                    bot_id,
                    {'drawdown': metrics.drawdown}
                ))
                self.last_triggered[rule_key] = current_time
    
    def _can_trigger_rule(self, rule_key: str, current_time: datetime) -> bool:
        """Check if rule can be triggered (cooldown check)"""
        if rule_key not in self.last_triggered:
            return True
        
        # Extract rule name for cooldown lookup
        rule_name = rule_key.split('_')[0] + '_' + rule_key.split('_')[1]
        cooldown = self.alert_rules.get(rule_name, {}).get('cooldown', 300)
        
        return (current_time - self.last_triggered[rule_key]).total_seconds() > cooldown


class RealTimeMonitor:
    """
    Real-time monitoring system for trading bots with alerts,
    performance tracking, and system health monitoring.
    """
    
    def __init__(self, safety_manager: SafetyManager):
        self.safety_manager = safety_manager
        self.alert_manager = AlertManager()
        
        # Monitored bots
        self.monitored_bots: Dict[str, TradingBot] = {}
        self.bot_metrics: Dict[str, PerformanceMetrics] = {}
        
        # WebSocket connections for real-time updates
        self.websocket_connections: Set[Any] = set()
        
        # Monitoring configuration
        self.monitoring_active = False
        self.update_interval = 5  # seconds
        self.metrics_history_size = 1000
        
        # Performance tracking
        self.metrics_history: Dict[str, List[PerformanceMetrics]] = {}
        
        # Event handlers
        self.event_handlers: Dict[MonitoringEvent, List[Callable]] = {}
        
        # System health
        self.system_health = {
            'last_update': datetime.utcnow(),
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'active_connections': 0,
            'error_rate': 0.0
        }
    
    def register_bot(self, bot: TradingBot):
        """Register a bot for monitoring"""
        self.monitored_bots[bot.bot_id] = bot
        self.metrics_history[bot.bot_id] = []
        
        # Set up bot event handlers
        bot.add_signal_handler(self._on_signal_generated)
        bot.add_trade_handler(self._on_trade_executed)
        bot.add_error_handler(self._on_bot_error)
        
        logger.info(f"Registered bot {bot.name} for real-time monitoring")
    
    def unregister_bot(self, bot_id: str):
        """Unregister a bot from monitoring"""
        if bot_id in self.monitored_bots:
            del self.monitored_bots[bot_id]
            if bot_id in self.bot_metrics:
                del self.bot_metrics[bot_id]
            if bot_id in self.metrics_history:
                del self.metrics_history[bot_id]
            
            logger.info(f"Unregistered bot {bot_id} from monitoring")
    
    async def start_monitoring(self):
        """Start real-time monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        logger.info("Started real-time monitoring system")
        
        # Start monitoring loop
        await self._monitoring_loop()
    
    async def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.monitoring_active = False
        logger.info("Stopped real-time monitoring system")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                current_time = datetime.utcnow()
                
                # Update bot metrics
                for bot_id, bot in self.monitored_bots.items():
                    await self._update_bot_metrics(bot, current_time)
                
                # Update system health
                await self._update_system_health()
                
                # Broadcast updates to WebSocket connections
                await self._broadcast_updates()
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)  # Wait before retrying
    
    async def _update_bot_metrics(self, bot: TradingBot, timestamp: datetime):
        """Update performance metrics for a bot"""
        try:
            # Calculate current metrics
            portfolio = bot.portfolio
            
            # Daily P&L calculation
            today_start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_trades = [
                trade for trade in portfolio.trades
                if trade.exit_time >= today_start
            ]
            daily_pnl = sum(trade.pnl for trade in daily_trades)
            
            # Drawdown calculation
            initial_value = getattr(bot, '_initial_portfolio_value', portfolio.total_value)
            peak_value = max(initial_value, portfolio.total_value)
            drawdown = (peak_value - portfolio.total_value) / peak_value if peak_value > 0 else 0
            
            # Win rate calculation
            if portfolio.trades:
                winning_trades = sum(1 for trade in portfolio.trades if trade.pnl > 0)
                win_rate = winning_trades / len(portfolio.trades)
            else:
                win_rate = 0
            
            # Strategy allocations (if available)
            strategy_allocations = {}
            if hasattr(bot, 'strategy_allocations'):
                strategy_allocations = bot.strategy_allocations
            
            # Create metrics object
            metrics = PerformanceMetrics(
                bot_id=bot.bot_id,
                timestamp=timestamp,
                portfolio_value=portfolio.total_value,
                total_pnl=portfolio.realized_pnl,
                daily_pnl=daily_pnl,
                unrealized_pnl=portfolio.unrealized_pnl,
                drawdown=drawdown,
                win_rate=win_rate,
                total_trades=len(portfolio.trades),
                active_positions=len(portfolio.positions),
                strategy_allocations=strategy_allocations
            )
            
            # Store current metrics
            self.bot_metrics[bot.bot_id] = metrics
            
            # Add to history
            if bot.bot_id not in self.metrics_history:
                self.metrics_history[bot.bot_id] = []
            
            self.metrics_history[bot.bot_id].append(metrics)
            
            # Trim history if needed
            if len(self.metrics_history[bot.bot_id]) > self.metrics_history_size:
                self.metrics_history[bot.bot_id] = self.metrics_history[bot.bot_id][-self.metrics_history_size:]
            
            # Check alert rules
            self.alert_manager.check_alert_rules(bot.bot_id, metrics)
            
            # Emit performance update event
            await self._emit_event(MonitoringEvent.PERFORMANCE_UPDATE, {
                'bot_id': bot.bot_id,
                'metrics': metrics.to_dict()
            })
            
        except Exception as e:
            logger.error(f"Error updating metrics for bot {bot.bot_id}: {e}")
    
    async def _update_system_health(self):
        """Update system health metrics"""
        try:
            import psutil
            
            self.system_health.update({
                'last_update': datetime.utcnow(),
                'cpu_usage': psutil.cpu_percent(),
                'memory_usage': psutil.virtual_memory().percent,
                'active_connections': len(self.websocket_connections),
                'monitored_bots': len(self.monitored_bots),
                'active_alerts': len(self.alert_manager.active_alerts)
            })
            
        except ImportError:
            # psutil not available, use basic metrics
            self.system_health.update({
                'last_update': datetime.utcnow(),
                'active_connections': len(self.websocket_connections),
                'monitored_bots': len(self.monitored_bots),
                'active_alerts': len(self.alert_manager.active_alerts)
            })
        except Exception as e:
            logger.error(f"Error updating system health: {e}")
    
    async def _broadcast_updates(self):
        """Broadcast updates to WebSocket connections"""
        if not self.websocket_connections:
            return
        
        try:
            # Prepare update message
            update_message = {
                'type': 'monitoring_update',
                'timestamp': datetime.utcnow().isoformat(),
                'system_health': self.system_health,
                'bot_metrics': {
                    bot_id: metrics.to_dict()
                    for bot_id, metrics in self.bot_metrics.items()
                },
                'active_alerts': [
                    alert.to_dict() for alert in self.alert_manager.get_active_alerts()
                ]
            }
            
            # Send to all connected clients
            disconnected = set()
            for websocket in self.websocket_connections:
                try:
                    await websocket.send_text(json.dumps(update_message))
                except Exception as e:
                    logger.warning(f"Failed to send update to WebSocket: {e}")
                    disconnected.add(websocket)
            
            # Remove disconnected clients
            self.websocket_connections -= disconnected
            
        except Exception as e:
            logger.error(f"Error broadcasting updates: {e}")
    
    async def _on_signal_generated(self, signal):
        """Handle signal generation event"""
        await self.alert_manager.trigger_alert(
            MonitoringEvent.SIGNAL_GENERATED,
            AlertLevel.INFO,
            "Signal Generated",
            f"New {signal.direction} signal for {signal.symbol}",
            getattr(signal, 'bot_id', None),
            {
                'symbol': signal.symbol,
                'direction': signal.direction,
                'confidence': signal.confidence,
                'strategy': signal.strategy
            }
        )
    
    async def _on_trade_executed(self, trade):
        """Handle trade execution event"""
        level = AlertLevel.INFO
        if trade.pnl < 0 and abs(trade.pnl_pct) > 5:
            level = AlertLevel.WARNING
        
        await self.alert_manager.trigger_alert(
            MonitoringEvent.TRADE_CLOSED,
            level,
            "Trade Executed",
            f"Trade closed: {trade.pnl:+.2f} ({trade.pnl_pct:+.1f}%)",
            getattr(trade, 'bot_id', None),
            {
                'symbol': trade.symbol,
                'pnl': trade.pnl,
                'pnl_pct': trade.pnl_pct,
                'strategy': trade.strategy
            }
        )
    
    async def _on_bot_error(self, error_message: str):
        """Handle bot error event"""
        await self.alert_manager.trigger_alert(
            MonitoringEvent.BOT_ERROR,
            AlertLevel.CRITICAL,
            "Bot Error",
            error_message,
            data={'error': error_message}
        )
    
    async def _emit_event(self, event_type: MonitoringEvent, data: Dict[str, Any]):
        """Emit monitoring event"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")
    
    def add_event_handler(self, event_type: MonitoringEvent, handler: Callable):
        """Add event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def add_websocket_connection(self, websocket):
        """Add WebSocket connection for real-time updates"""
        self.websocket_connections.add(websocket)
        logger.info(f"Added WebSocket connection. Total: {len(self.websocket_connections)}")
    
    def remove_websocket_connection(self, websocket):
        """Remove WebSocket connection"""
        self.websocket_connections.discard(websocket)
        logger.info(f"Removed WebSocket connection. Total: {len(self.websocket_connections)}")
    
    def get_bot_metrics(self, bot_id: str) -> Optional[PerformanceMetrics]:
        """Get current metrics for a bot"""
        return self.bot_metrics.get(bot_id)
    
    def get_bot_metrics_history(
        self, 
        bot_id: str, 
        limit: int = 100
    ) -> List[PerformanceMetrics]:
        """Get metrics history for a bot"""
        if bot_id not in self.metrics_history:
            return []
        
        return self.metrics_history[bot_id][-limit:]
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        return {
            'monitoring_active': self.monitoring_active,
            'monitored_bots': len(self.monitored_bots),
            'active_connections': len(self.websocket_connections),
            'active_alerts': len(self.alert_manager.active_alerts),
            'system_health': self.system_health,
            'last_update': datetime.utcnow().isoformat()
        }