from typing import Dict, Set, List
from fastapi import WebSocket
import asyncio
import json
from datetime import datetime

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and subscriptions"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
        self.symbol_subscribers: Dict[str, Set[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = set()
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from subscriptions
        if websocket in self.subscriptions:
            symbols = self.subscriptions[websocket]
            for symbol in symbols:
                if symbol in self.symbol_subscribers:
                    self.symbol_subscribers[symbol].discard(websocket)
                    if not self.symbol_subscribers[symbol]:
                        del self.symbol_subscribers[symbol]
            
            del self.subscriptions[websocket]
        
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")
    
    async def disconnect_all(self):
        """Disconnect all WebSocket connections"""
        for websocket in self.active_connections.copy():
            try:
                await websocket.close()
            except:
                pass
            self.disconnect(websocket)
    
    async def subscribe(self, websocket: WebSocket, symbol: str, interval: str):
        """Subscribe a connection to symbol updates"""
        subscription_key = f"{symbol}:{interval}"
        
        # Add to subscriptions
        self.subscriptions[websocket].add(subscription_key)
        
        # Add to symbol subscribers
        if subscription_key not in self.symbol_subscribers:
            self.symbol_subscribers[subscription_key] = set()
        self.symbol_subscribers[subscription_key].add(websocket)
        
        logger.info(f"WebSocket subscribed to {subscription_key}")
    
    async def unsubscribe(self, websocket: WebSocket, symbol: str):
        """Unsubscribe a connection from symbol updates"""
        # Remove all intervals for this symbol
        to_remove = []
        for sub in self.subscriptions.get(websocket, set()):
            if sub.startswith(f"{symbol}:"):
                to_remove.append(sub)
        
        for sub in to_remove:
            self.subscriptions[websocket].discard(sub)
            if sub in self.symbol_subscribers:
                self.symbol_subscribers[sub].discard(websocket)
                if not self.symbol_subscribers[sub]:
                    del self.symbol_subscribers[sub]
        
        logger.info(f"WebSocket unsubscribed from {symbol}")
    
    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        """Send message to specific connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")
            self.disconnect(websocket)
    
    async def broadcast_symbol_update(self, symbol: str, interval: str, data: Dict):
        """Broadcast update to all subscribers of a symbol"""
        subscription_key = f"{symbol}:{interval}"
        
        if subscription_key not in self.symbol_subscribers:
            return
        
        message = {
            "type": "price_update",
            "symbol": symbol,
            "interval": interval,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to all subscribers
        disconnected = []
        for websocket in self.symbol_subscribers[subscription_key]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)
    
    async def broadcast_indicator_update(self, symbol: str, interval: str, indicator: str, data: Dict):
        """Broadcast indicator update to subscribers"""
        subscription_key = f"{symbol}:{interval}"
        
        if subscription_key not in self.symbol_subscribers:
            return
        
        message = {
            "type": "indicator_update",
            "symbol": symbol,
            "interval": interval,
            "indicator": indicator,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        disconnected = []
        for websocket in self.symbol_subscribers[subscription_key]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting indicator update: {e}")
                disconnected.append(websocket)
        
        for websocket in disconnected:
            self.disconnect(websocket)
    
    async def broadcast_signal(self, symbol: str, signal: Dict):
        """Broadcast trading signal to all subscribers of the symbol"""
        # Send to all subscribers regardless of interval
        symbol_subscribers = set()
        for sub_key, subscribers in self.symbol_subscribers.items():
            if sub_key.startswith(f"{symbol}:"):
                symbol_subscribers.update(subscribers)
        
        if not symbol_subscribers:
            return
        
        message = {
            "type": "signal",
            "symbol": symbol,
            "signal": signal,
            "timestamp": datetime.now().isoformat()
        }
        
        disconnected = []
        for websocket in symbol_subscribers:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting signal: {e}")
                disconnected.append(websocket)
        
        for websocket in disconnected:
            self.disconnect(websocket)
    
    def get_connection_stats(self) -> Dict:
        """Get statistics about current connections"""
        total_subscriptions = sum(len(subs) for subs in self.subscriptions.values())
        
        return {
            "total_connections": len(self.active_connections),
            "total_subscriptions": total_subscriptions,
            "symbols_monitored": len(self.symbol_subscribers),
            "subscriptions_by_symbol": {
                symbol: len(subscribers)
                for symbol, subscribers in self.symbol_subscribers.items()
            }
        }