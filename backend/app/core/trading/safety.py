"""
Safety Guardrails and Kill Switches for Trading Bots.
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np

from app.core.trading.base import TradingBot, Portfolio, Order, Trade, BotStatus
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class TriggerType(Enum):
    """Safety trigger types"""
    DRAWDOWN = "drawdown"
    DAILY_LOSS = "daily_loss"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    POSITION_SIZE = "position_size"
    CORRELATION = "correlation"
    VOLATILITY = "volatility"
    EXCHANGE_ISSUES = "exchange_issues"
    MANUAL = "manual"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


@dataclass
class SafetyAlert:
    """Safety alert information"""
    id: str
    timestamp: datetime
    level: AlertLevel
    trigger_type: TriggerType
    bot_id: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    actions_taken: List[str] = field(default_factory=list)


@dataclass
class SafetyRule:
    """Safety rule configuration"""
    id: str
    name: str
    trigger_type: TriggerType
    enabled: bool = True
    threshold_value: float = 0.0
    time_window: int = 3600  # seconds
    action: str = "pause"  # pause, stop, alert
    cooldown_period: int = 300  # seconds before rule can trigger again
    last_triggered: Optional[datetime] = None


@dataclass
class KillSwitch:
    """Emergency kill switch configuration"""
    id: str
    name: str
    enabled: bool = True
    triggers: List[TriggerType] = field(default_factory=list)
    threshold: float = 0.0
    action: str = "stop_all"  # stop_all, pause_all, liquidate_all
    require_confirmation: bool = True
    auto_trigger: bool = False
    activated_at: Optional[datetime] = None
    activated_by: Optional[str] = None


class SafetyManager:
    """
    Comprehensive safety management system that monitors trading bots
    and implements automated safety measures.
    """
    
    def __init__(self):
        self.bots: Dict[str, TradingBot] = {}
        self.safety_rules: Dict[str, SafetyRule] = {}
        self.kill_switches: Dict[str, KillSwitch] = {}
        self.alerts: List[SafetyAlert] = []
        
        # Monitoring state
        self.monitoring_active = False
        self.monitor_interval = 10  # seconds
        self.last_check: Dict[str, datetime] = {}
        
        # Statistics
        self.total_alerts = 0
        self.total_interventions = 0
        self.bots_stopped_by_safety = 0
        
        # Event handlers
        self.alert_handlers: List[Callable] = []
        self.intervention_handlers: List[Callable] = []
        
        # Initialize default safety rules
        self._initialize_default_rules()
    
    def _initialize_default_rules(self):
        """Initialize default safety rules"""
        
        # Max drawdown rule
        self.safety_rules["max_drawdown"] = SafetyRule(
            id="max_drawdown",
            name="Maximum Drawdown Protection",
            trigger_type=TriggerType.DRAWDOWN,
            threshold_value=0.15,  # 15%
            action="pause",
            cooldown_period=3600  # 1 hour
        )
        
        # Daily loss limit
        self.safety_rules["daily_loss_limit"] = SafetyRule(
            id="daily_loss_limit",
            name="Daily Loss Limit",
            trigger_type=TriggerType.DAILY_LOSS,
            threshold_value=0.05,  # 5%
            time_window=86400,  # 24 hours
            action="pause",
            cooldown_period=3600
        )
        
        # Consecutive losses
        self.safety_rules["consecutive_losses"] = SafetyRule(
            id="consecutive_losses",
            name="Consecutive Losses Protection",
            trigger_type=TriggerType.CONSECUTIVE_LOSSES,
            threshold_value=5,  # 5 consecutive losses
            action="pause",
            cooldown_period=1800  # 30 minutes
        )
        
        # Large position size
        self.safety_rules["large_position"] = SafetyRule(
            id="large_position",
            name="Large Position Size Alert",
            trigger_type=TriggerType.POSITION_SIZE,
            threshold_value=0.25,  # 25% of portfolio
            action="alert",
            cooldown_period=300
        )
        
        # High correlation
        self.safety_rules["high_correlation"] = SafetyRule(
            id="high_correlation",
            name="High Correlation Warning",
            trigger_type=TriggerType.CORRELATION,
            threshold_value=0.8,  # 80% correlation
            action="alert",
            cooldown_period=1800
        )
        
        # Initialize default kill switches
        self._initialize_default_kill_switches()
    
    def _initialize_default_kill_switches(self):
        """Initialize default kill switches"""
        
        # Emergency stop
        self.kill_switches["emergency_stop"] = KillSwitch(
            id="emergency_stop",
            name="Emergency Stop All",
            triggers=[TriggerType.MANUAL],
            action="stop_all",
            require_confirmation=False,
            auto_trigger=False
        )
        
        # Catastrophic loss
        self.kill_switches["catastrophic_loss"] = KillSwitch(
            id="catastrophic_loss",
            name="Catastrophic Loss Protection",
            triggers=[TriggerType.DRAWDOWN, TriggerType.DAILY_LOSS],
            threshold=0.25,  # 25% loss
            action="stop_all",
            require_confirmation=False,
            auto_trigger=True
        )
        
        # Exchange issues
        self.kill_switches["exchange_issues"] = KillSwitch(
            id="exchange_issues",
            name="Exchange Connectivity Issues",
            triggers=[TriggerType.EXCHANGE_ISSUES],
            action="pause_all",
            require_confirmation=False,
            auto_trigger=True
        )
    
    def register_bot(self, bot: TradingBot):
        """Register a bot for safety monitoring"""
        self.bots[bot.bot_id] = bot
        self.last_check[bot.bot_id] = datetime.utcnow()
        logger.info(f"Registered bot {bot.name} ({bot.bot_id}) for safety monitoring")
    
    def unregister_bot(self, bot_id: str):
        """Unregister a bot from safety monitoring"""
        if bot_id in self.bots:
            del self.bots[bot_id]
            if bot_id in self.last_check:
                del self.last_check[bot_id]
            logger.info(f"Unregistered bot {bot_id} from safety monitoring")
    
    async def start_monitoring(self):
        """Start safety monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        logger.info("Started safety monitoring")
        
        # Start monitoring loop
        await self._monitoring_loop()
    
    async def stop_monitoring(self):
        """Stop safety monitoring"""
        self.monitoring_active = False
        logger.info("Stopped safety monitoring")
    
    async def _monitoring_loop(self):
        """Main safety monitoring loop"""
        while self.monitoring_active:
            try:
                current_time = datetime.utcnow()
                
                # Check each registered bot
                for bot_id, bot in self.bots.items():
                    await self._check_bot_safety(bot, current_time)
                
                # Check kill switches
                await self._check_kill_switches(current_time)
                
                # Clean up old alerts
                await self._cleanup_old_alerts()
                
                await asyncio.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"Error in safety monitoring loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _check_bot_safety(self, bot: TradingBot, current_time: datetime):
        """Check safety rules for a specific bot"""
        
        try:
            # Skip if bot is not running
            if bot.status != BotStatus.RUNNING:
                return
            
            # Check each safety rule
            for rule_id, rule in self.safety_rules.items():
                if not rule.enabled:
                    continue
                
                # Check cooldown
                if (rule.last_triggered and 
                    (current_time - rule.last_triggered).total_seconds() < rule.cooldown_period):
                    continue
                
                # Check rule condition
                triggered = await self._check_safety_rule(bot, rule, current_time)
                
                if triggered:
                    await self._handle_safety_trigger(bot, rule, current_time)
                    rule.last_triggered = current_time
        
        except Exception as e:
            logger.error(f"Error checking safety for bot {bot.bot_id}: {e}")
    
    async def _check_safety_rule(
        self, 
        bot: TradingBot, 
        rule: SafetyRule, 
        current_time: datetime
    ) -> bool:
        """Check if a safety rule is triggered"""
        
        try:
            if rule.trigger_type == TriggerType.DRAWDOWN:
                return await self._check_drawdown(bot, rule)
            
            elif rule.trigger_type == TriggerType.DAILY_LOSS:
                return await self._check_daily_loss(bot, rule, current_time)
            
            elif rule.trigger_type == TriggerType.CONSECUTIVE_LOSSES:
                return await self._check_consecutive_losses(bot, rule)
            
            elif rule.trigger_type == TriggerType.POSITION_SIZE:
                return await self._check_position_size(bot, rule)
            
            elif rule.trigger_type == TriggerType.CORRELATION:
                return await self._check_correlation(bot, rule)
            
            elif rule.trigger_type == TriggerType.VOLATILITY:
                return await self._check_volatility(bot, rule)
            
            elif rule.trigger_type == TriggerType.EXCHANGE_ISSUES:
                return await self._check_exchange_issues(bot, rule)
            
            elif rule.trigger_type == TriggerType.SUSPICIOUS_ACTIVITY:
                return await self._check_suspicious_activity(bot, rule)
        
        except Exception as e:
            logger.error(f"Error checking safety rule {rule.id}: {e}")
        
        return False
    
    async def _check_drawdown(self, bot: TradingBot, rule: SafetyRule) -> bool:
        """Check maximum drawdown"""
        if bot.portfolio.total_value <= 0:
            return False
        
        # Get initial value (simplified - would track from start)
        initial_value = getattr(bot, '_initial_portfolio_value', bot.portfolio.total_value)
        peak_value = max(initial_value, bot.portfolio.total_value)
        
        current_drawdown = (peak_value - bot.portfolio.total_value) / peak_value
        
        return current_drawdown >= rule.threshold_value
    
    async def _check_daily_loss(
        self, 
        bot: TradingBot, 
        rule: SafetyRule, 
        current_time: datetime
    ) -> bool:
        """Check daily loss limit"""
        
        # Get trades from today
        today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        today_trades = [
            trade for trade in bot.portfolio.trades
            if trade.exit_time >= today_start
        ]
        
        if not today_trades:
            return False
        
        daily_pnl = sum(trade.pnl for trade in today_trades)
        daily_loss_pct = abs(daily_pnl) / bot.portfolio.total_value if bot.portfolio.total_value > 0 else 0
        
        return daily_pnl < 0 and daily_loss_pct >= rule.threshold_value
    
    async def _check_consecutive_losses(self, bot: TradingBot, rule: SafetyRule) -> bool:
        """Check consecutive losses"""
        
        if len(bot.portfolio.trades) < rule.threshold_value:
            return False
        
        # Check last N trades
        recent_trades = bot.portfolio.trades[-int(rule.threshold_value):]
        
        return all(trade.pnl < 0 for trade in recent_trades)
    
    async def _check_position_size(self, bot: TradingBot, rule: SafetyRule) -> bool:
        """Check position size limits"""
        
        if bot.portfolio.total_value <= 0:
            return False
        
        for position in bot.portfolio.positions.values():
            position_value = position.size * position.current_price
            position_pct = position_value / bot.portfolio.total_value
            
            if position_pct >= rule.threshold_value:
                return True
        
        return False
    
    async def _check_correlation(self, bot: TradingBot, rule: SafetyRule) -> bool:
        """Check portfolio correlation"""
        
        # Simplified correlation check
        # In production, would calculate actual price correlations
        
        if len(bot.portfolio.positions) < 2:
            return False
        
        # Check for similar asset classes (simplified)
        symbols = list(bot.portfolio.positions.keys())
        crypto_count = sum(1 for symbol in symbols if any(base in symbol for base in ['BTC', 'ETH', 'BNB']))
        
        correlation_risk = crypto_count / len(symbols)
        
        return correlation_risk >= rule.threshold_value
    
    async def _check_volatility(self, bot: TradingBot, rule: SafetyRule) -> bool:
        """Check market volatility"""
        
        # Simplified volatility check
        # Would need historical price data for proper calculation
        
        return False  # Placeholder
    
    async def _check_exchange_issues(self, bot: TradingBot, rule: SafetyRule) -> bool:
        """Check for exchange connectivity issues"""
        
        try:
            # Test exchange connection
            if hasattr(bot.exchange, 'exchange') and bot.exchange.exchange:
                # Simple connectivity test
                await bot.exchange.exchange.fetch_status()
                return False
        except Exception:
            return True
        
        return False
    
    async def _check_suspicious_activity(self, bot: TradingBot, rule: SafetyRule) -> bool:
        """Check for suspicious activity patterns"""
        
        # Check for unusual trading patterns
        if len(bot.portfolio.trades) < 10:
            return False
        
        recent_trades = bot.portfolio.trades[-10:]
        
        # Check for rapid fire trading
        time_diffs = []
        for i in range(1, len(recent_trades)):
            diff = (recent_trades[i].entry_time - recent_trades[i-1].exit_time).total_seconds()
            time_diffs.append(diff)
        
        if time_diffs:
            avg_time_diff = sum(time_diffs) / len(time_diffs)
            if avg_time_diff < 60:  # Less than 1 minute between trades
                return True
        
        return False
    
    async def _handle_safety_trigger(
        self, 
        bot: TradingBot, 
        rule: SafetyRule, 
        current_time: datetime
    ):
        """Handle safety rule trigger"""
        
        # Create alert
        alert = SafetyAlert(
            id=str(uuid.uuid4()),
            timestamp=current_time,
            level=AlertLevel.WARNING if rule.action == "alert" else AlertLevel.CRITICAL,
            trigger_type=rule.trigger_type,
            bot_id=bot.bot_id,
            message=f"Safety rule '{rule.name}' triggered for bot {bot.name}"
        )
        
        self.alerts.append(alert)
        self.total_alerts += 1
        
        # Take action
        if rule.action == "pause":
            await bot.pause()
            alert.actions_taken.append("Bot paused")
            self.total_interventions += 1
            
        elif rule.action == "stop":
            await bot.stop()
            alert.actions_taken.append("Bot stopped")
            self.total_interventions += 1
            self.bots_stopped_by_safety += 1
            
        elif rule.action == "alert":
            alert.actions_taken.append("Alert generated")
        
        # Emit alert
        await self._emit_alert(alert)
        
        logger.warning(f"Safety intervention: {alert.message} - Actions: {alert.actions_taken}")
    
    async def _check_kill_switches(self, current_time: datetime):
        """Check kill switch conditions"""
        
        for switch_id, kill_switch in self.kill_switches.items():
            if not kill_switch.enabled or not kill_switch.auto_trigger:
                continue
            
            # Check if conditions are met
            triggered = await self._check_kill_switch_conditions(kill_switch, current_time)
            
            if triggered:
                await self._activate_kill_switch(kill_switch, current_time, "automatic")
    
    async def _check_kill_switch_conditions(
        self, 
        kill_switch: KillSwitch, 
        current_time: datetime
    ) -> bool:
        """Check if kill switch conditions are met"""
        
        # Check for catastrophic losses across all bots
        if TriggerType.DRAWDOWN in kill_switch.triggers:
            total_loss = 0
            total_value = 0
            
            for bot in self.bots.values():
                initial_value = getattr(bot, '_initial_portfolio_value', bot.portfolio.total_value)
                total_loss += max(0, initial_value - bot.portfolio.total_value)
                total_value += initial_value
            
            if total_value > 0:
                loss_pct = total_loss / total_value
                if loss_pct >= kill_switch.threshold:
                    return True
        
        # Check for exchange issues
        if TriggerType.EXCHANGE_ISSUES in kill_switch.triggers:
            exchange_issues = 0
            for bot in self.bots.values():
                try:
                    if hasattr(bot.exchange, 'exchange'):
                        await bot.exchange.exchange.fetch_status()
                except:
                    exchange_issues += 1
            
            if exchange_issues >= len(self.bots) * 0.5:  # 50% of bots have issues
                return True
        
        return False
    
    async def _activate_kill_switch(
        self, 
        kill_switch: KillSwitch, 
        current_time: datetime, 
        activated_by: str
    ):
        """Activate a kill switch"""
        
        if kill_switch.activated_at:
            return  # Already activated
        
        kill_switch.activated_at = current_time
        kill_switch.activated_by = activated_by
        
        # Create emergency alert
        alert = SafetyAlert(
            id=str(uuid.uuid4()),
            timestamp=current_time,
            level=AlertLevel.EMERGENCY,
            trigger_type=TriggerType.MANUAL,
            bot_id="ALL",
            message=f"Kill switch '{kill_switch.name}' activated by {activated_by}"
        )
        
        # Take action
        if kill_switch.action == "stop_all":
            for bot in self.bots.values():
                await bot.stop()
            alert.actions_taken.append(f"Stopped {len(self.bots)} bots")
            
        elif kill_switch.action == "pause_all":
            for bot in self.bots.values():
                await bot.pause()
            alert.actions_taken.append(f"Paused {len(self.bots)} bots")
            
        elif kill_switch.action == "liquidate_all":
            for bot in self.bots.values():
                # Close all positions
                try:
                    await self._liquidate_bot_positions(bot)
                except Exception as e:
                    logger.error(f"Error liquidating positions for bot {bot.bot_id}: {e}")
            alert.actions_taken.append("Liquidated all positions")
        
        self.alerts.append(alert)
        self.total_interventions += 1
        
        # Emit alert
        await self._emit_alert(alert)
        
        logger.critical(f"KILL SWITCH ACTIVATED: {kill_switch.name} - {alert.actions_taken}")
    
    async def _liquidate_bot_positions(self, bot: TradingBot):
        """Liquidate all positions for a bot"""
        
        for symbol, position in bot.portfolio.positions.items():
            try:
                # Create market sell order
                from app.core.trading.base import Order, OrderType, OrderSide
                
                order = Order(
                    id=str(uuid.uuid4()),
                    symbol=symbol,
                    type=OrderType.MARKET,
                    side=OrderSide.SELL if position.side == 'long' else OrderSide.BUY,
                    amount=position.size
                )
                
                await bot.exchange.place_order(order)
                logger.info(f"Liquidated position in {symbol} for bot {bot.bot_id}")
                
            except Exception as e:
                logger.error(f"Failed to liquidate position in {symbol}: {e}")
    
    async def manual_kill_switch(self, switch_id: str, user_id: str = "manual") -> bool:
        """Manually activate a kill switch"""
        
        if switch_id not in self.kill_switches:
            return False
        
        kill_switch = self.kill_switches[switch_id]
        
        if kill_switch.activated_at:
            return False  # Already activated
        
        await self._activate_kill_switch(kill_switch, datetime.utcnow(), user_id)
        return True
    
    async def reset_kill_switch(self, switch_id: str) -> bool:
        """Reset a kill switch"""
        
        if switch_id not in self.kill_switches:
            return False
        
        kill_switch = self.kill_switches[switch_id]
        kill_switch.activated_at = None
        kill_switch.activated_by = None
        
        logger.info(f"Reset kill switch: {kill_switch.name}")
        return True
    
    async def _emit_alert(self, alert: SafetyAlert):
        """Emit alert to handlers"""
        
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")
    
    async def _cleanup_old_alerts(self):
        """Remove old alerts to prevent memory buildup"""
        
        cutoff_time = datetime.utcnow() - timedelta(days=7)  # Keep 7 days
        self.alerts = [alert for alert in self.alerts if alert.timestamp > cutoff_time]
    
    def add_alert_handler(self, handler: Callable):
        """Add alert handler"""
        self.alert_handlers.append(handler)
    
    def add_intervention_handler(self, handler: Callable):
        """Add intervention handler"""
        self.intervention_handlers.append(handler)
    
    def get_alerts(
        self, 
        level: Optional[AlertLevel] = None, 
        limit: int = 100
    ) -> List[SafetyAlert]:
        """Get recent alerts"""
        
        alerts = self.alerts
        
        if level:
            alerts = [alert for alert in alerts if alert.level == level]
        
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda x: x.timestamp, reverse=True)
        
        return alerts[:limit]
    
    def get_safety_status(self) -> Dict[str, Any]:
        """Get overall safety status"""
        
        active_bots = len([bot for bot in self.bots.values() if bot.status == BotStatus.RUNNING])
        paused_bots = len([bot for bot in self.bots.values() if bot.status == BotStatus.PAUSED])
        stopped_bots = len([bot for bot in self.bots.values() if bot.status == BotStatus.STOPPED])
        
        active_alerts = len([alert for alert in self.alerts if not alert.acknowledged])
        critical_alerts = len([
            alert for alert in self.alerts 
            if alert.level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY] and not alert.acknowledged
        ])
        
        active_kill_switches = len([
            ks for ks in self.kill_switches.values() 
            if ks.activated_at is not None
        ])
        
        return {
            'monitoring_active': self.monitoring_active,
            'total_bots': len(self.bots),
            'active_bots': active_bots,
            'paused_bots': paused_bots,
            'stopped_bots': stopped_bots,
            'total_alerts': self.total_alerts,
            'active_alerts': active_alerts,
            'critical_alerts': critical_alerts,
            'total_interventions': self.total_interventions,
            'bots_stopped_by_safety': self.bots_stopped_by_safety,
            'active_kill_switches': active_kill_switches,
            'safety_rules_count': len(self.safety_rules),
            'kill_switches_count': len(self.kill_switches)
        }