"""
Demo data source for testing when external APIs are unavailable
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncio

from app.data.sources.base import DataSource
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class DemoDataSource(DataSource):
    """Demo data source that generates synthetic market data"""
    
    def __init__(self):
        super().__init__('demo')
        self.symbols = {
            'BTC-USDT': {'base_price': 50000, 'volatility': 0.03},
            'ETH-USDT': {'base_price': 3000, 'volatility': 0.04},
            'BNB-USDT': {'base_price': 400, 'volatility': 0.025},
            'ADA-USDT': {'base_price': 0.5, 'volatility': 0.05},
            'SOL-USDT': {'base_price': 100, 'volatility': 0.045},
            'AAPL': {'base_price': 175, 'volatility': 0.015},
            'GOOGL': {'base_price': 150, 'volatility': 0.02},
            'MSFT': {'base_price': 400, 'volatility': 0.015},
            'TSLA': {'base_price': 250, 'volatility': 0.04},
            'AMZN': {'base_price': 170, 'volatility': 0.025}
        }
    
    async def connect(self) -> bool:
        """Connect to demo data source"""
        self.connected = True
        logger.info("Demo data source connected")
        return True
    
    async def disconnect(self):
        """Disconnect from demo data source"""
        self.connected = False
        logger.info("Demo data source disconnected")
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1h',
        limit: int = 500,
        since: Optional[int] = None
    ) -> pd.DataFrame:
        """Fetch OHLCV data"""
        # Convert symbol format
        symbol = symbol.replace('/', '-')
        
        if symbol not in self.symbols:
            # Try without -USDT suffix for stocks
            base_symbol = symbol.replace('-USDT', '')
            if base_symbol not in self.symbols:
                raise ValueError(f"Symbol {symbol} not available in demo data")
            symbol = base_symbol
        
        config = self.symbols[symbol]
        base_price = config['base_price']
        volatility = config['volatility']
        
        # Parse timeframe
        timeframe_map = {
            '1m': 1, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '4h': 240, '1d': 1440
        }
        minutes = timeframe_map.get(timeframe, 60)
        
        # Generate timestamps
        end_time = datetime.utcnow()
        timestamps = []
        for i in range(limit):
            timestamps.append(end_time - timedelta(minutes=minutes * i))
        timestamps.reverse()
        
        # Generate price data with realistic patterns
        np.random.seed(42)  # For reproducibility
        prices = []
        volumes = []
        
        # Starting price with some randomness
        current_price = base_price * (1 + np.random.uniform(-0.02, 0.02))
        
        for i, ts in enumerate(timestamps):
            # Add trend component
            trend = np.sin(i / 50) * 0.001  # Slow wave
            
            # Add volatility
            change = np.random.normal(trend, volatility / np.sqrt(24 * 60 / minutes))
            current_price *= (1 + change)
            
            # Ensure price stays reasonable
            current_price = max(current_price, base_price * 0.5)
            current_price = min(current_price, base_price * 2.0)
            
            # Generate OHLC from price
            open_price = current_price * (1 + np.random.uniform(-0.001, 0.001))
            close_price = current_price * (1 + np.random.uniform(-0.001, 0.001))
            high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.002))
            low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.002))
            
            # Volume with some correlation to price movement
            base_volume = 1000000 if 'USDT' in symbol else 10000
            volume = base_volume * (1 + abs(change) * 10) * np.random.uniform(0.5, 1.5)
            
            prices.append({
                'timestamp': ts,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            })
        
        df = pd.DataFrame(prices)
        df.set_index('timestamp', inplace=True)
        df.index = pd.to_datetime(df.index)
        
        return df
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker data"""
        # Convert symbol format
        symbol = symbol.replace('/', '-')
        
        if symbol not in self.symbols:
            base_symbol = symbol.replace('-USDT', '')
            if base_symbol not in self.symbols:
                raise ValueError(f"Symbol {symbol} not available in demo data")
            symbol = base_symbol
        
        # Get latest price from OHLCV data
        df = await self.fetch_ohlcv(symbol, '1m', limit=2)
        latest = df.iloc[-1]
        previous = df.iloc[-2]
        
        change = latest['close'] - previous['close']
        change_pct = (change / previous['close']) * 100
        
        return {
            'symbol': symbol,
            'bid': latest['close'] * 0.9995,
            'ask': latest['close'] * 1.0005,
            'last': latest['close'],
            'volume': latest['volume'],
            'timestamp': latest.name.timestamp() * 1000,
            'change': change,
            'percentage': change_pct,
            'high': latest['high'],
            'low': latest['low']
        }
    
    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """Fetch order book data"""
        ticker = await self.fetch_ticker(symbol)
        last_price = ticker['last']
        
        # Generate realistic order book
        bids = []
        asks = []
        
        for i in range(limit):
            # Bids (buy orders)
            bid_price = last_price * (1 - 0.0001 * (i + 1))
            bid_volume = np.random.uniform(0.1, 2.0) * (limit - i) / limit
            bids.append([bid_price, bid_volume])
            
            # Asks (sell orders)
            ask_price = last_price * (1 + 0.0001 * (i + 1))
            ask_volume = np.random.uniform(0.1, 2.0) * (limit - i) / limit
            asks.append([ask_price, ask_volume])
        
        return {
            'symbol': symbol,
            'bids': bids,
            'asks': asks,
            'timestamp': datetime.utcnow().timestamp() * 1000
        }
    
    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols"""
        return list(self.symbols.keys())
    
    def get_available_timeframes(self) -> List[str]:
        """Get list of available timeframes"""
        return ['1m', '5m', '15m', '30m', '1h', '4h', '1d']