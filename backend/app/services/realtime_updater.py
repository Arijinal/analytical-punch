"""
Real-time price update service for WebSocket clients.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Set
import pandas as pd

from app.data.parallel_manager import parallel_data_manager
from app.api.websocket import ConnectionManager
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class RealTimeUpdater:
    """Service to provide real-time price updates via WebSocket."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.active_symbols: Dict[str, asyncio.Task] = {}
        self.update_intervals = {
            '1m': 10,   # Update every 10 seconds for 1m
            '5m': 30,   # Update every 30 seconds for 5m
            '15m': 60,  # Update every minute for 15m
            '30m': 60,  # Update every minute for 30m
            '1h': 60,   # Update every minute for 1h
            '4h': 300,  # Update every 5 minutes for 4h
            '1d': 600   # Update every 10 minutes for 1d
        }
    
    async def start_updates(self, symbol: str, interval: str):
        """Start real-time updates for a symbol."""
        task_key = f"{symbol}:{interval}"
        
        # Check if updates already running
        if task_key in self.active_symbols:
            return
        
        # Start update task
        task = asyncio.create_task(
            self._update_loop(symbol, interval)
        )
        self.active_symbols[task_key] = task
        logger.info(f"Started real-time updates for {task_key}")
    
    async def stop_updates(self, symbol: str, interval: str):
        """Stop real-time updates for a symbol."""
        task_key = f"{symbol}:{interval}"
        
        if task_key in self.active_symbols:
            task = self.active_symbols[task_key]
            task.cancel()
            del self.active_symbols[task_key]
            logger.info(f"Stopped real-time updates for {task_key}")
    
    async def _update_loop(self, symbol: str, interval: str):
        """Main update loop for a symbol."""
        update_interval = self.update_intervals.get(interval, 60)
        
        try:
            while True:
                try:
                    # Fetch latest data
                    latest_data = await self._fetch_latest_data(symbol, interval)
                    
                    if latest_data is not None:
                        # Broadcast to subscribers
                        await self.connection_manager.broadcast_symbol_update(
                            symbol, interval, latest_data
                        )
                    
                except Exception as e:
                    logger.error(f"Error updating {symbol}:{interval}: {e}")
                
                # Wait for next update
                await asyncio.sleep(update_interval)
                
        except asyncio.CancelledError:
            logger.info(f"Update loop cancelled for {symbol}:{interval}")
            raise
    
    async def _fetch_latest_data(self, symbol: str, interval: str) -> Dict:
        """Fetch the latest price data for a symbol."""
        try:
            # Fetch just the latest few candles
            df = await parallel_data_manager.fetch_ohlcv_parallel(
                symbol=symbol,
                timeframe=interval,
                limit=5  # Just latest 5 candles
            )
            
            if df.empty:
                return None
            
            # Get the latest candle
            latest = df.iloc[-1]
            
            # Check if this is a partial candle (still forming)
            now = datetime.now()
            candle_time = pd.Timestamp(latest.name).to_pydatetime()
            
            # Determine if candle is complete based on interval
            interval_minutes = {
                '1m': 1, '5m': 5, '15m': 15, '30m': 30,
                '1h': 60, '4h': 240, '1d': 1440
            }
            
            minutes = interval_minutes.get(interval, 60)
            is_complete = (now - candle_time) >= timedelta(minutes=minutes)
            
            return {
                'time': candle_time.isoformat(),
                'open': float(latest['open']),
                'high': float(latest['high']),
                'low': float(latest['low']),
                'close': float(latest['close']),
                'volume': float(latest['volume']),
                'is_complete': is_complete,
                'source': df.attrs.get('source', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error fetching latest data for {symbol}: {e}")
            return None
    
    async def check_subscriptions(self):
        """Periodically check and clean up subscriptions."""
        while True:
            try:
                # Get current subscriptions
                current_subs = set()
                for sub_key in self.connection_manager.symbol_subscribers.keys():
                    current_subs.add(sub_key)
                
                # Stop updates for symbols with no subscribers
                for task_key in list(self.active_symbols.keys()):
                    if task_key not in current_subs:
                        symbol, interval = task_key.split(':')
                        await self.stop_updates(symbol, interval)
                
                # Start updates for new subscriptions
                for sub_key in current_subs:
                    if sub_key not in self.active_symbols:
                        symbol, interval = sub_key.split(':')
                        await self.start_updates(symbol, interval)
                
            except Exception as e:
                logger.error(f"Error in subscription check: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def shutdown(self):
        """Shutdown all update tasks."""
        logger.info("Shutting down real-time updater")
        
        # Cancel all tasks
        for task in self.active_symbols.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self.active_symbols:
            await asyncio.gather(
                *self.active_symbols.values(),
                return_exceptions=True
            )
        
        self.active_symbols.clear()


# Global instance will be created in main.py
realtime_updater = None