"""
Kraken API data source for cryptocurrency data
Public endpoints don't require API keys and have generous rate limits
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


class KrakenDataSource(DataSource):
    """Kraken API data source for cryptocurrency data"""
    
    def __init__(self):
        super().__init__('kraken')
        self.base_url = 'https://api.kraken.com/0/public'
        self.session = None
        self.rate_limit_delay = 0.1  # Conservative rate limiting
        self.last_request_time = 0
        
        # Symbol mapping from common formats to Kraken pairs
        self.symbol_map = {
            'BTC-USDT': 'XBTUSD',
            'BTC/USDT': 'XBTUSD',
            'BTCUSDT': 'XBTUSD',
            'BTC': 'XBTUSD',
            'BTC-USD': 'XBTUSD',
            'BTC/USD': 'XBTUSD',
            'BTCUSD': 'XBTUSD',
            'ETH-USDT': 'ETHUSD',
            'ETH/USDT': 'ETHUSD',
            'ETHUSDT': 'ETHUSD',
            'ETH': 'ETHUSD',
            'ETH-USD': 'ETHUSD',
            'ETH/USD': 'ETHUSD',
            'ETHUSD': 'ETHUSD',
            'ADA-USDT': 'ADAUSD',
            'ADA/USDT': 'ADAUSD',
            'ADAUSDT': 'ADAUSD',
            'ADA': 'ADAUSD',
            'ADA-USD': 'ADAUSD',
            'ADA/USD': 'ADAUSD',
            'ADAUSD': 'ADAUSD',
            'DOT-USDT': 'DOTUSD',
            'DOT/USDT': 'DOTUSD',
            'DOTUSDT': 'DOTUSD',
            'DOT': 'DOTUSD',
            'DOT-USD': 'DOTUSD',
            'DOT/USD': 'DOTUSD',
            'DOTUSD': 'DOTUSD',
            'LINK-USDT': 'LINKUSD',
            'LINK/USDT': 'LINKUSD',
            'LINKUSDT': 'LINKUSD',
            'LINK': 'LINKUSD',
            'LINK-USD': 'LINKUSD',
            'LINK/USD': 'LINKUSD',
            'LINKUSD': 'LINKUSD',
            'LTC-USDT': 'LTCUSD',
            'LTC/USDT': 'LTCUSD',
            'LTCUSDT': 'LTCUSD',
            'LTC': 'LTCUSD',
            'LTC-USD': 'LTCUSD',
            'LTC/USD': 'LTCUSD',
            'LTCUSD': 'LTCUSD',
            'XRP-USDT': 'XRPUSD',
            'XRP/USDT': 'XRPUSD',
            'XRPUSDT': 'XRPUSD',
            'XRP': 'XRPUSD',
            'XRP-USD': 'XRPUSD',
            'XRP/USD': 'XRPUSD',
            'XRPUSD': 'XRPUSD',
            'BCH-USDT': 'BCHUSD',
            'BCH/USDT': 'BCHUSD',
            'BCHUSDT': 'BCHUSD',
            'BCH': 'BCHUSD',
            'BCH-USD': 'BCHUSD',
            'BCH/USD': 'BCHUSD',
            'BCHUSD': 'BCHUSD'
        }
        
        # Kraken timeframe mapping
        self.timeframe_map = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240,
            '1d': 1440,
            '1w': 10080,
            '2w': 21600
        }
    
    async def connect(self) -> bool:
        """Connect to Kraken API"""
        try:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'Analytical-Punch/1.0'
                }
            )
            
            # Test connection with server time
            await self._rate_limit()
            async with self.session.get(f'{self.base_url}/Time') as response:
                if response.status == 200:
                    data = await response.json()
                    if 'error' in data and not data['error']:
                        self.connected = True
                        logger.info("Kraken API connected successfully")
                        return True
                    else:
                        logger.error(f"Kraken API error: {data.get('error', 'Unknown error')}")
                        return False
                else:
                    logger.error(f"Kraken API connection failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to connect to Kraken API: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Kraken API"""
        if self.session:
            await self.session.close()
            self.session = None
        self.connected = False
        logger.info("Kraken API disconnected")
    
    async def _rate_limit(self):
        """Implement rate limiting"""
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    def _get_kraken_pair(self, symbol: str) -> str:
        """Convert symbol to Kraken pair format"""
        symbol = symbol.upper()
        return self.symbol_map.get(symbol, symbol)
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1h',
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = 500
    ) -> pd.DataFrame:
        """Fetch OHLCV data from Kraken"""
        if not self.session:
            raise RuntimeError("Not connected to Kraken API")
        
        kraken_pair = self._get_kraken_pair(symbol)
        interval = self.timeframe_map.get(timeframe, 60)
        
        await self._rate_limit()
        
        url = f'{self.base_url}/OHLC'
        params = {
            'pair': kraken_pair,
            'interval': interval
        }
        
        # Add since parameter if provided (convert from datetime)
        if start_time:
            params['since'] = int(start_time.timestamp())
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Kraken API error {response.status}: {text}")
                
                data = await response.json()
                
                if data.get('error'):
                    raise Exception(f"Kraken API error: {', '.join(data['error'])}")
                
                if 'result' not in data:
                    raise Exception("Invalid response format from Kraken")
                
                result = data['result']
                
                # Get the pair data (Kraken returns normalized pair names)
                pair_data = None
                for key, value in result.items():
                    if key != 'last' and isinstance(value, list):
                        pair_data = value
                        break
                
                if not pair_data:
                    raise Exception(f"No OHLC data found for {kraken_pair}")
                
                # Convert to DataFrame
                df_data = []
                for ohlc in pair_data[-limit:]:  # Limit to requested number of candles
                    timestamp = datetime.fromtimestamp(float(ohlc[0]))
                    df_data.append({
                        'timestamp': timestamp,
                        'open': float(ohlc[1]),
                        'high': float(ohlc[2]),
                        'low': float(ohlc[3]),
                        'close': float(ohlc[4]),
                        'volume': float(ohlc[6])  # Volume weighted average price is at index 5
                    })
                
                df = pd.DataFrame(df_data)
                df.set_index('timestamp', inplace=True)
                df.index = pd.to_datetime(df.index)
                
                return df
                
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol} from Kraken: {e}")
            raise
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker data from Kraken"""
        if not self.session:
            raise RuntimeError("Not connected to Kraken API")
        
        kraken_pair = self._get_kraken_pair(symbol)
        
        await self._rate_limit()
        
        url = f'{self.base_url}/Ticker'
        params = {'pair': kraken_pair}
        
        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"Kraken API error {response.status}: {text}")
            
            data = await response.json()
            
            if data.get('error'):
                raise Exception(f"Kraken API error: {', '.join(data['error'])}")
            
            if 'result' not in data:
                raise Exception("Invalid response format from Kraken")
            
            result = data['result']
            
            # Get ticker data for the pair
            ticker_data = None
            for key, value in result.items():
                if isinstance(value, dict):
                    ticker_data = value
                    break
            
            if not ticker_data:
                raise Exception(f"No ticker data found for {kraken_pair}")
            
            # Parse Kraken ticker format
            last_price = float(ticker_data['c'][0])  # Last trade price
            bid_price = float(ticker_data['b'][0])   # Best bid price
            ask_price = float(ticker_data['a'][0])   # Best ask price
            volume_24h = float(ticker_data['v'][1])  # 24h volume
            high_24h = float(ticker_data['h'][1])    # 24h high
            low_24h = float(ticker_data['l'][1])     # 24h low
            open_24h = float(ticker_data['o'])       # Opening price
            
            # Calculate 24h change
            change_24h = last_price - open_24h
            change_pct = (change_24h / open_24h) * 100 if open_24h > 0 else 0
            
            return {
                'symbol': symbol,
                'bid': bid_price,
                'ask': ask_price,
                'last': last_price,
                'volume': volume_24h,
                'timestamp': int(time.time() * 1000),
                'change': change_24h,
                'percentage': change_pct,
                'high': high_24h,
                'low': low_24h
            }
    
    async def fetch_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Fetch order book data from Kraken"""
        if not self.session:
            raise RuntimeError("Not connected to Kraken API")
        
        kraken_pair = self._get_kraken_pair(symbol)
        
        await self._rate_limit()
        
        url = f'{self.base_url}/Depth'
        params = {
            'pair': kraken_pair,
            'count': min(limit, 500)  # Kraken max is 500
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"Kraken API error {response.status}: {text}")
            
            data = await response.json()
            
            if data.get('error'):
                raise Exception(f"Kraken API error: {', '.join(data['error'])}")
            
            if 'result' not in data:
                raise Exception("Invalid response format from Kraken")
            
            result = data['result']
            
            # Get order book data for the pair
            orderbook_data = None
            for key, value in result.items():
                if isinstance(value, dict) and 'asks' in value and 'bids' in value:
                    orderbook_data = value
                    break
            
            if not orderbook_data:
                raise Exception(f"No order book data found for {kraken_pair}")
            
            # Format bids and asks
            bids = [[float(bid[0]), float(bid[1])] for bid in orderbook_data['bids']]
            asks = [[float(ask[0]), float(ask[1])] for ask in orderbook_data['asks']]
            
            return {
                'symbol': symbol,
                'bids': bids,
                'asks': asks,
                'timestamp': int(time.time() * 1000)
            }
    
    async def get_symbols(self) -> List[str]:
        """Get available trading pairs from Kraken"""
        if not self.session:
            await self.connect()
        
        await self._rate_limit()
        
        url = f'{self.base_url}/AssetPairs'
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return list(self.symbol_map.keys())  # Fallback to our mapped symbols
                
                data = await response.json()
                
                if data.get('error'):
                    return list(self.symbol_map.keys())
                
                if 'result' not in data:
                    return list(self.symbol_map.keys())
                
                # Extract USD pairs from Kraken response
                kraken_pairs = data['result']
                symbols = []
                
                for pair_name, pair_info in kraken_pairs.items():
                    if 'USD' in pair_name and pair_info.get('status') == 'online':
                        # Convert back to our standard format
                        base = pair_info.get('base', '')
                        if base:
                            symbols.extend([
                                f"{base}-USD",
                                f"{base}/USD",
                                f"{base}USD"
                            ])
                
                # Combine with our predefined symbols
                all_symbols = list(set(symbols + list(self.symbol_map.keys())))
                return sorted(all_symbols)
                
        except Exception as e:
            logger.error(f"Error fetching symbols from Kraken: {e}")
            return list(self.symbol_map.keys())
    
    def is_symbol_valid(self, symbol: str) -> bool:
        """Check if symbol is valid for Kraken"""
        symbol = symbol.upper()
        return symbol in self.symbol_map or any(
            usd_variant in symbol for usd_variant in ['USD', 'USDT']
        )
    
    async def get_server_time(self) -> int:
        """Get Kraken server time"""
        if not self.session:
            raise RuntimeError("Not connected to Kraken API")
        
        await self._rate_limit()
        
        url = f'{self.base_url}/Time'
        
        async with self.session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Kraken API error {response.status}")
            
            data = await response.json()
            
            if data.get('error'):
                raise Exception(f"Kraken API error: {', '.join(data['error'])}")
            
            return data['result']['unixtime']