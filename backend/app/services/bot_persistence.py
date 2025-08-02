"""
Bot state persistence service for saving and restoring trading bot states.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import pickle
import base64

from sqlalchemy.orm import Session
from app.database.trading_db import trading_db
from app.models.trading import TradingBot, Position, Order, Trade
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class BotPersistenceService:
    """Service to persist and restore trading bot states."""
    
    async def save_bot_state(self, bot_id: str, bot_state: Dict[str, Any]) -> bool:
        """Save the complete state of a trading bot."""
        try:
            with trading_db.get_session() as session:
                # Find or create bot record
                bot = session.query(TradingBot).filter_by(id=bot_id).first()
                
                if not bot:
                    bot = TradingBot(id=bot_id)
                    session.add(bot)
                
                # Update bot fields
                bot.name = bot_state.get('name', 'Unnamed Bot')
                bot.description = bot_state.get('description', '')
                bot.status = bot_state.get('status', 'stopped')
                bot.paper_trading = bot_state.get('paper_trading', True)
                
                # Configuration
                bot.config = bot_state.get('config', {})
                bot.strategies = bot_state.get('strategies', [])
                bot.symbols = bot_state.get('symbols', [])
                bot.timeframes = bot_state.get('timeframes', ['1h'])
                
                # Performance metrics
                bot.initial_capital = bot_state.get('initial_capital', 10000)
                bot.current_capital = bot_state.get('current_capital', 10000)
                bot.total_pnl = bot_state.get('total_pnl', 0)
                bot.total_return_pct = bot_state.get('total_return_pct', 0)
                bot.max_drawdown = bot_state.get('max_drawdown', 0)
                bot.total_trades = bot_state.get('total_trades', 0)
                bot.winning_trades = bot_state.get('winning_trades', 0)
                bot.win_rate = bot_state.get('win_rate', 0)
                bot.profit_factor = bot_state.get('profit_factor', 0)
                bot.sharpe_ratio = bot_state.get('sharpe_ratio', 0)
                
                # Risk management
                bot.max_position_size = bot_state.get('max_position_size', 0.1)
                bot.max_daily_loss = bot_state.get('max_daily_loss', 0.05)
                bot.max_drawdown_limit = bot_state.get('max_drawdown_limit', 0.15)
                
                # Save strategy allocations and performance
                if 'strategy_allocations' in bot_state:
                    bot.config['strategy_allocations'] = bot_state['strategy_allocations']
                
                if 'strategy_performance' in bot_state:
                    bot.config['strategy_performance'] = bot_state['strategy_performance']
                
                # Save portfolio state
                if 'portfolio' in bot_state:
                    bot.config['portfolio_state'] = {
                        'cash': bot_state['portfolio'].get('cash', 10000),
                        'total_value': bot_state['portfolio'].get('total_value', 10000),
                        'equity_curve': bot_state['portfolio'].get('equity_curve', []),
                        'timestamps': [ts.isoformat() if hasattr(ts, 'isoformat') else ts 
                                     for ts in bot_state['portfolio'].get('timestamps', [])]
                    }
                
                session.commit()
                logger.info(f"Successfully saved state for bot {bot_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving bot state: {e}")
            return False
    
    async def restore_bot_state(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Restore the state of a trading bot."""
        try:
            with trading_db.get_session() as session:
                bot = session.query(TradingBot).filter_by(id=bot_id).first()
                
                if not bot:
                    logger.warning(f"Bot {bot_id} not found in database")
                    return None
                
                # Reconstruct bot state
                bot_state = {
                    'bot_id': bot.id,
                    'name': bot.name,
                    'description': bot.description,
                    'status': bot.status.value if hasattr(bot.status, 'value') else bot.status,
                    'paper_trading': bot.paper_trading,
                    
                    # Configuration
                    'config': bot.config or {},
                    'strategies': bot.strategies or [],
                    'symbols': bot.symbols or [],
                    'timeframes': bot.timeframes or ['1h'],
                    
                    # Performance metrics
                    'initial_capital': bot.initial_capital,
                    'current_capital': bot.current_capital,
                    'total_pnl': bot.total_pnl,
                    'total_return_pct': bot.total_return_pct,
                    'max_drawdown': bot.max_drawdown,
                    'total_trades': bot.total_trades,
                    'winning_trades': bot.winning_trades,
                    'win_rate': bot.win_rate,
                    'profit_factor': bot.profit_factor,
                    'sharpe_ratio': bot.sharpe_ratio,
                    
                    # Risk management
                    'max_position_size': bot.max_position_size,
                    'max_daily_loss': bot.max_daily_loss,
                    'max_drawdown_limit': bot.max_drawdown_limit,
                    
                    # Timestamps
                    'created_at': bot.created_at.isoformat() if bot.created_at else None,
                    'started_at': bot.started_at.isoformat() if bot.started_at else None,
                    'stopped_at': bot.stopped_at.isoformat() if bot.stopped_at else None,
                }
                
                # Restore strategy allocations
                if 'strategy_allocations' in bot.config:
                    bot_state['strategy_allocations'] = bot.config['strategy_allocations']
                
                # Restore strategy performance
                if 'strategy_performance' in bot.config:
                    bot_state['strategy_performance'] = bot.config['strategy_performance']
                
                # Restore portfolio state
                if 'portfolio_state' in bot.config:
                    portfolio_state = bot.config['portfolio_state']
                    bot_state['portfolio'] = {
                        'cash': portfolio_state.get('cash', 10000),
                        'total_value': portfolio_state.get('total_value', 10000),
                        'equity_curve': portfolio_state.get('equity_curve', []),
                        'timestamps': [datetime.fromisoformat(ts) if isinstance(ts, str) else ts
                                     for ts in portfolio_state.get('timestamps', [])]
                    }
                
                # Load open positions
                positions = session.query(Position).filter_by(bot_id=bot_id).all()
                bot_state['open_positions'] = [
                    {
                        'id': pos.id,
                        'symbol': pos.symbol,
                        'side': pos.side,
                        'size': pos.size,
                        'entry_price': pos.entry_price,
                        'current_price': pos.current_price,
                        'unrealized_pnl': pos.unrealized_pnl,
                        'stop_loss': pos.stop_loss,
                        'take_profit': pos.take_profit,
                        'entry_time': pos.entry_time.isoformat() if pos.entry_time else None,
                    }
                    for pos in positions
                ]
                
                # Detach positions from session to avoid binding issues
                for pos in positions:
                    session.expunge(pos)
                
                logger.info(f"Successfully restored state for bot {bot_id}")
                return bot_state
                
        except Exception as e:
            logger.error(f"Error restoring bot state: {e}")
            return None
    
    async def list_saved_bots(self) -> List[Dict[str, Any]]:
        """List all saved bot states."""
        try:
            with trading_db.get_session() as session:
                bots = session.query(TradingBot).all()
                
                # Convert to list of dictionaries to avoid session binding issues
                result = [
                    {
                        'bot_id': bot.id,
                        'name': bot.name,
                        'status': bot.status.value if hasattr(bot.status, 'value') else bot.status,
                        'paper_trading': bot.paper_trading,
                        'current_capital': bot.current_capital,
                        'total_return_pct': bot.total_return_pct,
                        'created_at': bot.created_at.isoformat() if bot.created_at else None,
                        'last_active': bot.updated_at.isoformat() if bot.updated_at else None,
                    }
                    for bot in bots
                ]
                
                # Detach bots from session to avoid binding issues
                for bot in bots:
                    session.expunge(bot)
                
                return result
                
        except Exception as e:
            logger.error(f"Error listing saved bots: {e}")
            return []
    
    async def delete_bot_state(self, bot_id: str) -> bool:
        """Delete a saved bot state."""
        try:
            with trading_db.get_session() as session:
                bot = session.query(TradingBot).filter_by(id=bot_id).first()
                
                if bot:
                    session.delete(bot)
                    session.commit()
                    logger.info(f"Deleted bot state for {bot_id}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error deleting bot state: {e}")
            return False
    
    async def save_checkpoint(self, bot_id: str, checkpoint_data: Dict[str, Any]) -> bool:
        """Save a checkpoint of bot state for recovery."""
        try:
            checkpoint = {
                'bot_id': bot_id,
                'timestamp': datetime.now().isoformat(),
                'data': checkpoint_data
            }
            
            # Serialize checkpoint
            serialized = base64.b64encode(
                pickle.dumps(checkpoint)
            ).decode('utf-8')
            
            with trading_db.get_session() as session:
                bot = session.query(TradingBot).filter_by(id=bot_id).first()
                
                if bot:
                    if 'checkpoints' not in bot.config:
                        bot.config['checkpoints'] = []
                    
                    # Keep only last 10 checkpoints
                    checkpoints = bot.config['checkpoints']
                    checkpoints.append({
                        'timestamp': checkpoint['timestamp'],
                        'data': serialized
                    })
                    
                    if len(checkpoints) > 10:
                        checkpoints = checkpoints[-10:]
                    
                    bot.config['checkpoints'] = checkpoints
                    session.commit()
                    
                    logger.info(f"Saved checkpoint for bot {bot_id}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
            return False
    
    async def restore_checkpoint(self, bot_id: str, timestamp: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Restore bot state from a checkpoint."""
        try:
            with trading_db.get_session() as session:
                bot = session.query(TradingBot).filter_by(id=bot_id).first()
                
                if not bot or 'checkpoints' not in bot.config:
                    return None
                
                checkpoints = bot.config['checkpoints']
                
                if not checkpoints:
                    return None
                
                # Get specific checkpoint or latest
                if timestamp:
                    checkpoint = next(
                        (cp for cp in checkpoints if cp['timestamp'] == timestamp),
                        None
                    )
                else:
                    checkpoint = checkpoints[-1]
                
                if checkpoint:
                    # Deserialize checkpoint
                    serialized = checkpoint['data']
                    data = pickle.loads(base64.b64decode(serialized))
                    
                    logger.info(f"Restored checkpoint for bot {bot_id} from {checkpoint['timestamp']}")
                    return data['data']
                
                return None
                
        except Exception as e:
            logger.error(f"Error restoring checkpoint: {e}")
            return None


# Create singleton instance
bot_persistence = BotPersistenceService()