"""
API endpoints for trading bot management.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import uuid

from app.config import get_config
from app.database.trading_db import (
    bot_repository, order_repository, trade_repository,
    position_repository, alert_repository, log_repository
)
from app.core.trading.adaptive_bot import AdaptiveMultiStrategyBot
from app.core.trading.exchange import BinanceExchange
from app.core.trading.paper_trader import PaperTradingEngine
from app.core.trading.safety import SafetyManager
from app.utils.logger import setup_logger

config = get_config()
logger = setup_logger(__name__)

router = APIRouter()

# Global instances
active_bots: Dict[str, AdaptiveMultiStrategyBot] = {}
paper_engine = PaperTradingEngine(BinanceExchange(paper_trading=True))
safety_manager = SafetyManager()


# Pydantic models
class BotConfig(BaseModel):
    name: str = Field(..., description="Bot name")
    description: Optional[str] = Field(None, description="Bot description")
    symbols: List[str] = Field(..., description="Trading symbols")
    timeframes: List[str] = Field(default=['1h', '4h'], description="Timeframes")
    paper_trading: bool = Field(True, description="Paper trading mode")
    initial_capital: float = Field(10000, description="Initial capital")
    
    # Risk management
    max_position_size: float = Field(0.1, description="Max position size")
    max_daily_loss: float = Field(0.05, description="Max daily loss")
    max_drawdown: float = Field(0.15, description="Max drawdown")
    max_open_positions: int = Field(5, description="Max open positions")
    
    # Strategy parameters
    momentum_params: Optional[Dict[str, Any]] = None
    value_params: Optional[Dict[str, Any]] = None
    breakout_params: Optional[Dict[str, Any]] = None
    trend_params: Optional[Dict[str, Any]] = None
    
    # Update intervals
    update_interval: int = Field(300, description="Update interval in seconds")
    rebalance_interval: int = Field(3600, description="Rebalance interval in seconds")


class BotUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_position_size: Optional[float] = None
    max_daily_loss: Optional[float] = None
    max_drawdown: Optional[float] = None


class OrderRequest(BaseModel):
    symbol: str
    side: str  # 'buy' or 'sell'
    amount: float
    order_type: str = 'market'
    price: Optional[float] = None


class SafetyRuleUpdate(BaseModel):
    enabled: bool
    threshold_value: Optional[float] = None
    action: Optional[str] = None


@router.post("/bots", response_model=Dict[str, Any])
async def create_bot(config: BotConfig, background_tasks: BackgroundTasks):
    """Create a new trading bot"""
    try:
        # Create bot in database
        bot_data = {
            'name': config.name,
            'description': config.description,
            'config': config.dict(),
            'strategies': ['momentum_punch', 'value_punch', 'breakout_punch', 'trend_punch'],
            'symbols': config.symbols,
            'timeframes': config.timeframes,
            'paper_trading': config.paper_trading,
            'initial_capital': config.initial_capital,
            'current_capital': config.initial_capital,
            'max_position_size': config.max_position_size,
            'max_daily_loss': config.max_daily_loss,
            'max_drawdown_limit': config.max_drawdown
        }
        
        db_bot = bot_repository.create_bot(bot_data)
        
        # Extract values from the returned dictionary
        bot_id = db_bot['id']
        bot_name = db_bot['name']
        created_at = db_bot['created_at']
        
        # Create bot instance with filtered config
        # Only pass the required parameters to avoid unexpected keyword arguments
        filtered_config = {
            'paper_trading': config.paper_trading,
            'initial_capital': config.initial_capital,
            'max_position_size': config.max_position_size,
            'max_daily_loss': config.max_daily_loss,
            'max_drawdown': config.max_drawdown,
            'max_open_positions': config.max_open_positions,
            'update_interval': config.update_interval,
            'rebalance_interval': config.rebalance_interval,
            'momentum_params': config.momentum_params,
            'value_params': config.value_params,
            'breakout_params': config.breakout_params,
            'trend_params': config.trend_params
        }
        
        try:
            bot_instance = AdaptiveMultiStrategyBot(
                bot_id=bot_id,
                name=bot_name,
                config=filtered_config,
                symbols=config.symbols,
                timeframes=config.timeframes
            )
        except Exception as e:
            logger.error(f"Error creating AdaptiveMultiStrategyBot: {e}")
            logger.error(f"Config: {filtered_config}")
            logger.error(f"Symbols: {config.symbols}")
            logger.error(f"Timeframes: {config.timeframes}")
            raise
        
        # Store in active bots
        active_bots[bot_id] = bot_instance
        
        # Register with safety manager
        safety_manager.register_bot(bot_instance)
        
        # Log creation
        log_repository.log_event(
            level='INFO',
            component='api',
            event='bot_created',
            message=f"Created trading bot {config.name}",
            bot_id=bot_id
        )
        
        return {
            'bot_id': bot_id,
            'name': bot_name,
            'status': 'created',
            'paper_trading': config.paper_trading,
            'symbols': config.symbols,
            'created_at': created_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error creating bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots", response_model=List[Dict[str, Any]])
async def get_bots(active_only: bool = Query(False, description="Get only active bots")):
    """Get all trading bots"""
    try:
        bots = bot_repository.get_all_bots(active_only=active_only)
        
        result = []
        for bot in bots:
            bot_data = {
                'bot_id': bot['id'],
                'name': bot['name'],
                'description': bot['description'],
                'status': bot['status'].value if hasattr(bot['status'], 'value') else bot['status'],
                'paper_trading': bot['paper_trading'],
                'symbols': bot['symbols'],
                'timeframes': bot['timeframes'],
                'initial_capital': bot['initial_capital'],
                'current_capital': bot['current_capital'],
                'total_pnl': bot['total_pnl'],
                'total_return_pct': bot['total_return_pct'],
                'max_drawdown': bot['max_drawdown'],
                'total_trades': bot['total_trades'],
                'win_rate': bot['win_rate'],
                'created_at': bot['created_at'].isoformat() if bot['created_at'] else None,
                'started_at': bot['started_at'].isoformat() if bot['started_at'] else None,
                'stopped_at': bot['stopped_at'].isoformat() if bot['stopped_at'] else None
            }
            
            # Add real-time status if bot is active
            if bot['id'] in active_bots:
                live_status = active_bots[bot['id']].get_detailed_status()
                bot_data.update({
                    'live_status': live_status,
                    'portfolio_value': live_status.get('portfolio_value', 0),
                    'open_positions': live_status.get('positions', 0)
                })
            
            result.append(bot_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting bots: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}", response_model=Dict[str, Any])
async def get_bot(bot_id: str):
    """Get specific trading bot details"""
    try:
        bot = bot_repository.get_bot(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Get performance data
        performance = bot_repository.get_bot_performance(bot_id)
        
        result = {
            'bot_id': bot.id,
            'name': bot.name,
            'description': bot.description,
            'status': bot.status.value,
            'config': bot.config,
            'strategies': bot.strategies,
            'symbols': bot.symbols,
            'timeframes': bot.timeframes,
            'paper_trading': bot.paper_trading,
            'performance': performance,
            'created_at': bot.created_at.isoformat(),
            'updated_at': bot.updated_at.isoformat()
        }
        
        # Add live data if bot is active
        if bot_id in active_bots:
            result['live_status'] = active_bots[bot_id].get_detailed_status()
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/bots/{bot_id}", response_model=Dict[str, Any])
async def update_bot(bot_id: str, updates: BotUpdate):
    """Update trading bot configuration"""
    try:
        bot = bot_repository.get_bot(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Check if bot is running
        if bot_id in active_bots and active_bots[bot_id].status.value == 'running':
            raise HTTPException(status_code=400, detail="Cannot update running bot")
        
        # Update database
        update_data = updates.dict(exclude_unset=True)
        bot_repository.update_bot(bot_id, update_data)
        
        # Log update
        log_repository.log_event(
            level='INFO',
            component='api',
            event='bot_updated',
            message=f"Updated bot {bot.name}",
            bot_id=bot_id,
            data=update_data
        )
        
        return {'message': 'Bot updated successfully', 'bot_id': bot_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bots/{bot_id}")
async def delete_bot(bot_id: str):
    """Delete trading bot"""
    try:
        bot = bot_repository.get_bot(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Stop bot if running
        if bot_id in active_bots:
            await active_bots[bot_id].stop()
            safety_manager.unregister_bot(bot_id)
            del active_bots[bot_id]
        
        # Delete from database
        bot_repository.delete_bot(bot_id)
        
        # Log deletion
        log_repository.log_event(
            level='INFO',
            component='api',
            event='bot_deleted',
            message=f"Deleted bot {bot.name}",
            bot_id=bot_id
        )
        
        return {'message': 'Bot deleted successfully', 'bot_id': bot_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/start")
async def start_bot(bot_id: str, background_tasks: BackgroundTasks):
    """Start trading bot"""
    try:
        bot = bot_repository.get_bot(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        if bot_id in active_bots:
            bot_instance = active_bots[bot_id]
            
            # Start bot in background
            background_tasks.add_task(bot_instance.start)
            
            # Update database
            bot_repository.update_bot(bot_id, {
                'status': 'running',
                'started_at': datetime.utcnow()
            })
            
            # Log start
            log_repository.log_event(
                level='INFO',
                component='api',
                event='bot_started',
                message=f"Started bot {bot.name}",
                bot_id=bot_id
            )
            
            return {'message': 'Bot start initiated', 'bot_id': bot_id}
        else:
            raise HTTPException(status_code=400, detail="Bot instance not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/stop")
async def stop_bot(bot_id: str):
    """Stop trading bot"""
    try:
        bot = bot_repository.get_bot(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        if bot_id in active_bots:
            bot_instance = active_bots[bot_id]
            await bot_instance.stop()
            
            # Update database
            bot_repository.update_bot(bot_id, {
                'status': 'stopped',
                'stopped_at': datetime.utcnow()
            })
            
            # Log stop
            log_repository.log_event(
                level='INFO',
                component='api',
                event='bot_stopped',
                message=f"Stopped bot {bot.name}",
                bot_id=bot_id
            )
            
            return {'message': 'Bot stopped successfully', 'bot_id': bot_id}
        else:
            raise HTTPException(status_code=400, detail="Bot not running")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/pause")
async def pause_bot(bot_id: str):
    """Pause trading bot"""
    try:
        if bot_id not in active_bots:
            raise HTTPException(status_code=400, detail="Bot not running")
        
        bot_instance = active_bots[bot_id]
        await bot_instance.pause()
        
        # Update database
        bot_repository.update_bot(bot_id, {'status': 'paused'})
        
        return {'message': 'Bot paused successfully', 'bot_id': bot_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/resume")
async def resume_bot(bot_id: str):
    """Resume trading bot"""
    try:
        if bot_id not in active_bots:
            raise HTTPException(status_code=400, detail="Bot not running")
        
        bot_instance = active_bots[bot_id]
        await bot_instance.resume()
        
        # Update database
        bot_repository.update_bot(bot_id, {'status': 'running'})
        
        return {'message': 'Bot resumed successfully', 'bot_id': bot_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}/positions", response_model=List[Dict[str, Any]])
async def get_bot_positions(bot_id: str):
    """Get bot positions"""
    try:
        positions = position_repository.get_bot_positions(bot_id)
        
        result = []
        for position in positions:
            result.append({
                'id': position.id,
                'symbol': position.symbol,
                'side': position.side,
                'size': position.size,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'unrealized_pnl': position.unrealized_pnl,
                'unrealized_pnl_pct': position.unrealized_pnl_pct,
                'entry_time': position.entry_time.isoformat(),
                'strategy': position.strategy,
                'stop_loss': position.stop_loss,
                'take_profit': position.take_profit
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting positions for bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}/trades", response_model=List[Dict[str, Any]])
async def get_bot_trades(
    bot_id: str,
    limit: int = Query(100, description="Number of trades to return"),
    strategy: Optional[str] = Query(None, description="Filter by strategy")
):
    """Get bot trade history"""
    try:
        trades = trade_repository.get_bot_trades(bot_id, limit=limit, strategy=strategy)
        
        result = []
        for trade in trades:
            result.append({
                'id': trade.id,
                'symbol': trade.symbol,
                'side': trade.side,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'size': trade.size,
                'pnl': trade.pnl,
                'pnl_pct': trade.pnl_pct,
                'commission': trade.commission,
                'entry_time': trade.entry_time.isoformat(),
                'exit_time': trade.exit_time.isoformat(),
                'duration_seconds': trade.duration_seconds,
                'exit_reason': trade.exit_reason,
                'strategy': trade.strategy,
                'confidence': trade.confidence,
                'risk_reward_ratio': trade.risk_reward_ratio
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting trades for bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}/orders", response_model=List[Dict[str, Any]])
async def get_bot_orders(
    bot_id: str,
    active_only: bool = Query(False, description="Get only active orders"),
    limit: int = Query(100, description="Number of orders to return")
):
    """Get bot order history"""
    try:
        orders = order_repository.get_bot_orders(bot_id, active_only=active_only, limit=limit)
        
        result = []
        for order in orders:
            result.append({
                'id': order.id,
                'symbol': order.symbol,
                'type': order.type.value,
                'side': order.side.value,
                'amount': order.amount,
                'price': order.price,
                'status': order.status.value,
                'filled_amount': order.filled_amount,
                'filled_price': order.filled_price,
                'commission': order.commission,
                'created_at': order.created_at.isoformat(),
                'updated_at': order.updated_at.isoformat(),
                'filled_at': order.filled_at.isoformat() if order.filled_at else None,
                'strategy': order.strategy,
                'exchange_order_id': order.exchange_order_id
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting orders for bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/orders")
async def place_manual_order(bot_id: str, order_request: OrderRequest):
    """Place manual order for bot"""
    try:
        if bot_id not in active_bots:
            raise HTTPException(status_code=400, detail="Bot not active")
        
        bot_instance = active_bots[bot_id]
        
        # Create order through bot's exchange
        from app.core.trading.base import Order, OrderType, OrderSide
        
        order = Order(
            id=str(uuid.uuid4()),
            symbol=order_request.symbol,
            type=OrderType(order_request.order_type),
            side=OrderSide(order_request.side),
            amount=order_request.amount,
            price=order_request.price
        )
        
        # Place order
        order_id = await bot_instance.exchange.place_order(order)
        
        # Log manual order
        log_repository.log_event(
            level='INFO',
            component='api',
            event='manual_order',
            message=f"Manual order placed: {order_request.side} {order_request.amount} {order_request.symbol}",
            bot_id=bot_id,
            symbol=order_request.symbol,
            data=order_request.dict()
        )
        
        return {
            'message': 'Order placed successfully',
            'order_id': order_id,
            'bot_id': bot_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error placing manual order for bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}/performance", response_model=Dict[str, Any])
async def get_bot_performance(bot_id: str):
    """Get detailed bot performance metrics"""
    try:
        performance = bot_repository.get_bot_performance(bot_id)
        
        if not performance:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Get strategy-specific performance
        strategies = ['momentum_punch', 'value_punch', 'breakout_punch', 'trend_punch']
        strategy_performance = {}
        
        for strategy in strategies:
            strategy_perf = trade_repository.get_strategy_performance(bot_id, strategy)
            if strategy_perf:
                strategy_performance[strategy] = strategy_perf
        
        performance['strategy_performance'] = strategy_performance
        
        return performance
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting performance for bot {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts", response_model=List[Dict[str, Any]])
async def get_alerts(
    bot_id: Optional[str] = Query(None, description="Filter by bot ID"),
    level: Optional[str] = Query(None, description="Filter by alert level"),
    unacknowledged_only: bool = Query(False, description="Get only unacknowledged alerts"),
    limit: int = Query(100, description="Number of alerts to return")
):
    """Get safety alerts"""
    try:
        alerts = alert_repository.get_alerts(
            bot_id=bot_id,
            level=level,
            unacknowledged_only=unacknowledged_only,
            limit=limit
        )
        
        result = []
        for alert in alerts:
            result.append({
                'id': alert.id,
                'bot_id': alert.bot_id,
                'level': alert.level.value,
                'trigger_type': alert.trigger_type,
                'message': alert.message,
                'data': alert.data,
                'actions_taken': alert.actions_taken,
                'acknowledged': alert.acknowledged,
                'acknowledged_by': alert.acknowledged_by,
                'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                'timestamp': alert.timestamp.isoformat(),
                'created_at': alert.created_at.isoformat()
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, acknowledged_by: str = "api_user"):
    """Acknowledge a safety alert"""
    try:
        success = alert_repository.acknowledge_alert(alert_id, acknowledged_by)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {'message': 'Alert acknowledged successfully', 'alert_id': alert_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/safety/status", response_model=Dict[str, Any])
async def get_safety_status():
    """Get overall safety system status"""
    try:
        return safety_manager.get_safety_status()
        
    except Exception as e:
        logger.error(f"Error getting safety status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/safety/kill-switch/{switch_id}")
async def activate_kill_switch(switch_id: str, user_id: str = "api_user"):
    """Manually activate a kill switch"""
    try:
        success = await safety_manager.manual_kill_switch(switch_id, user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Kill switch not found or already activated")
        
        return {'message': f'Kill switch {switch_id} activated', 'activated_by': user_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating kill switch {switch_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paper-trading/accounts", response_model=List[Dict[str, Any]])
async def get_paper_accounts():
    """Get paper trading accounts"""
    try:
        # This would typically come from database
        # For now, return global stats from paper engine
        stats = paper_engine.get_global_stats()
        
        return [{
            'global_stats': stats,
            'total_accounts': stats.get('total_accounts', 0),
            'active_accounts': stats.get('active_accounts', 0),
            'total_trades': stats.get('total_trades', 0)
        }]
        
    except Exception as e:
        logger.error(f"Error getting paper accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/paper-trading/accounts")
async def create_paper_account(
    initial_balance: float = 100000,
    commission_rate: float = 0.001,
    slippage_rate: float = 0.0005
):
    """Create a new paper trading account"""
    try:
        account_id = await paper_engine.create_account(
            initial_balance=initial_balance,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate
        )
        
        return {
            'account_id': account_id,
            'initial_balance': initial_balance,
            'commission_rate': commission_rate,
            'slippage_rate': slippage_rate
        }
        
    except Exception as e:
        logger.error(f"Error creating paper account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/status", response_model=Dict[str, Any])
async def get_system_status():
    """Get overall trading system status"""
    try:
        return {
            'active_bots': len(active_bots),
            'running_bots': len([b for b in active_bots.values() if b.status.value == 'running']),
            'paused_bots': len([b for b in active_bots.values() if b.status.value == 'paused']),
            'safety_monitoring': safety_manager.monitoring_active,
            'paper_trading_available': True,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))