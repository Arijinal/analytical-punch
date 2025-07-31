"""
CoinGecko API data source for cryptocurrency data
Free tier: 100 calls/minute, no API key required
"""

import asyncio
import aiohttp
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import time

from app.data.sources.base import DataSource
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class CoinGeckoDataSource(DataSource):
    """CoinGecko API data source for cryptocurrency data"""
    
    def __init__(self):
        super().__init__('coingecko')
        self.base_url = 'https://api.coingecko.com/api/v3'
        self.session = None
        self.rate_limit_delay = 0.6  # 100 calls/minute = 0.6s between calls
        self.last_request_time = 0
        
        # Symbol mapping from common formats to CoinGecko IDs
        self.symbol_map = {
            'BTC-USDT': 'bitcoin',
            'BTC/USDT': 'bitcoin',
            'BTCUSDT': 'bitcoin',
            'BTC': 'bitcoin',
            'ETH-USDT': 'ethereum',
            'ETH/USDT': 'ethereum',
            'ETHUSDT': 'ethereum',
            'ETH': 'ethereum',
            'BNB-USDT': 'binancecoin',
            'BNB/USDT': 'binancecoin',
            'BNBUSDT': 'binancecoin',
            'BNB': 'binancecoin',
            'ADA-USDT': 'cardano',
            'ADA/USDT': 'cardano',
            'ADAUSDT': 'cardano',
            'ADA': 'cardano',
            'SOL-USDT': 'solana',
            'SOL/USDT': 'solana',
            'SOLUSDT': 'solana',
            'SOL': 'solana',
            'DOT-USDT': 'polkadot',
            'DOT/USDT': 'polkadot',
            'DOTUSDT': 'polkadot',
            'DOT': 'polkadot',
            'AVAX-USDT': 'avalanche-2',
            'AVAX/USDT': 'avalanche-2',
            'AVAXUSDT': 'avalanche-2',
            'AVAX': 'avalanche-2',
            'MATIC-USDT': 'matic-network',
            'MATIC/USDT': 'matic-network',
            'MATICUSDT': 'matic-network',
            'MATIC': 'matic-network',
            'LINK-USDT': 'chainlink',
            'LINK/USDT': 'chainlink',
            'LINKUSDT': 'chainlink',
            'LINK': 'chainlink',
            'UNI-USDT': 'uniswap',
            'UNI/USDT': 'uniswap',
            'UNIUSDT': 'uniswap',
            'UNI': 'uniswap'
        }
        
        # Timeframe mapping
        self.timeframe_map = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240,
            '1d': 1440,
            '1w': 10080,
            '1M': 43200
        }
    
    async def connect(self) -> bool:
        """Connect to CoinGecko API"""
        try:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'Analytical-Punch/1.0',
                    'Accept': 'application/json'
                }
            )
            
            # Test connection with a simple ping
            await self._rate_limit()
            async with self.session.get(f'{self.base_url}/ping') as response:
                if response.status == 200:
                    self.connected = True
                    logger.info("CoinGecko API connected successfully")
                    return True
                else:
                    logger.error(f"CoinGecko API connection failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to connect to CoinGecko API: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from CoinGecko API"""
        if self.session:
            await self.session.close()
            self.session = None
        self.connected = False
        logger.info("CoinGecko API disconnected")
    
    async def _rate_limit(self):
        """Implement rate limiting"""
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    def _get_coin_id(self, symbol: str) -> str:
        """Convert symbol to CoinGecko coin ID"""
        symbol = symbol.upper()
        return self.symbol_map.get(symbol, symbol.lower())
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1h',
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = 500
    ) -> pd.DataFrame:
        """Fetch OHLCV data from CoinGecko"""
        if not self.session:
            raise RuntimeError("Not connected to CoinGecko API")
        
        coin_id = self._get_coin_id(symbol)
        
        try:
            # For 1m to 1h: use market_chart endpoint with minutely data
            # For 4h+: use OHLC endpoint
            if timeframe in ['1m', '5m', '15m', '30m', '1h']:
                return await self._fetch_market_chart(coin_id, timeframe, limit)
            else:
                return await self._fetch_ohlc_data(coin_id, timeframe, limit)
                
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            raise
    
    async def _fetch_market_chart(self, coin_id: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Fetch data using market_chart endpoint (better for short timeframes)"""
        await self._rate_limit()
        
        # Calculate days needed
        minutes_per_candle = self.timeframe_map[timeframe]
        days = max(1, (limit * minutes_per_candle) // (24 * 60))
        
        url = f'{self.base_url}/coins/{coin_id}/market_chart'
        params = {
            'vs_currency': 'usd',
            'days': min(days, 90),  # CoinGecko free tier limit
            # Don't specify interval - let CoinGecko auto-select based on days
            # 'interval': 'minutely' if timeframe in ['1m', '5m'] else 'hourly'
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"CoinGecko API error {response.status}: {text}")
            
            data = await response.json()
            
            if 'prices' not in data:
                raise Exception("Invalid response format from CoinGecko")
            
            # Convert to DataFrame
            prices = data['prices']
            volumes = data.get('total_volumes', [])
            
            df_data = []
            for i, price_point in enumerate(prices):
                timestamp = datetime.fromtimestamp(price_point[0] / 1000)
                price = price_point[1]
                volume = volumes[i][1] if i < len(volumes) else 0
                
                df_data.append({
                    'timestamp': timestamp,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': volume
                })
            
            df = pd.DataFrame(df_data)
            
            # Resample to requested timeframe if needed
            if timeframe != '1m':
                df = self._resample_data(df, timeframe)
            
            # Limit to requested number of candles
            df = df.tail(limit).copy()
            
            return df
    
    async def _fetch_ohlc_data(self, coin_id: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Fetch data using OHLC endpoint (better for longer timeframes)"""
        await self._rate_limit()
        
        # Calculate days needed
        if timeframe == '1d':
            days = min(limit, 90)  # CoinGecko free tier limit
        elif timeframe == '1w':
            days = min(limit * 7, 365)
        else:  # 4h
            days = min((limit * 4) // 24, 90)
        
        url = f'{self.base_url}/coins/{coin_id}/ohlc'
        params = {
            'vs_currency': 'usd',
            'days': days
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"CoinGecko API error {response.status}: {text}")
            
            data = await response.json()
            
            df_data = []
            for ohlc in data:
                timestamp = datetime.fromtimestamp(ohlc[0] / 1000)
                df_data.append({
                    'timestamp': timestamp,
                    'open': ohlc[1],
                    'high': ohlc[2],
                    'low': ohlc[3],
                    'close': ohlc[4],
                    'volume': 0  # OHLC endpoint doesn't provide volume
                })
            
            df = pd.DataFrame(df_data)
            df.set_index('timestamp', inplace=True)
            df.index = pd.to_datetime(df.index)
            
            # Limit to requested number of candles
            df = df.tail(limit).copy()
            
            return df
    
    def _resample_data(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Resample 1-minute data to requested timeframe"""
        df.set_index('timestamp', inplace=True)
        
        # Resample rules
        rule_map = {
            '5m': '5T',
            '15m': '15T',
            '30m': '30T',
            '1h': '1H',
            '4h': '4H',
            '1d': '1D'
        }
        
        rule = rule_map.get(timeframe, '1H')
        
        resampled = df.resample(rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        resampled.reset_index(inplace=True)
        return resampled
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker data"""
        if not self.session:
            raise RuntimeError("Not connected to CoinGecko API")
        
        coin_id = self._get_coin_id(symbol)
        
        await self._rate_limit()
        
        url = f'{self.base_url}/simple/price'
        params = {
            'ids': coin_id,
            'vs_currencies': 'usd',
            'include_24hr_change': 'true',
            'include_24hr_vol': 'true',
            'include_last_updated_at': 'true'
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"CoinGecko API error {response.status}: {text}")
            
            data = await response.json()
            
            if coin_id not in data:
                raise Exception(f"Symbol {symbol} not found on CoinGecko")
            
            coin_data = data[coin_id]
            
            return {
                'symbol': symbol,
                'bid': coin_data['usd'] * 0.9995,  # Approximate bid
                'ask': coin_data['usd'] * 1.0005,  # Approximate ask
                'last': coin_data['usd'],
                'volume': coin_data.get('usd_24h_vol', 0),
                'timestamp': coin_data.get('last_updated_at', int(time.time())) * 1000,
                'change': coin_data.get('usd_24h_change', 0),
                'percentage': coin_data.get('usd_24h_change', 0),
                'high': coin_data['usd'],  # Would need market chart for accurate high/low
                'low': coin_data['usd']
            }
    
    async def get_symbols(self) -> List[str]:
        """Get available symbols"""
        return list(self.symbol_map.keys())
    
    def is_symbol_valid(self, symbol: str) -> bool:
        """Check if symbol is valid"""
        return symbol.upper() in self.symbol_map
    
    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """Fetch order book (not available in CoinGecko free tier)"""
        raise NotImplementedError("Order book data not available in CoinGecko free tier")