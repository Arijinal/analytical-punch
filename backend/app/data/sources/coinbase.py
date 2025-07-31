"""
Coinbase Advanced API data source for cryptocurrency data
Public endpoints don't require authentication for market data
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


class CoinbaseDataSource(DataSource):
    """Coinbase Advanced API data source for cryptocurrency data"""
    
    def __init__(self):
        super().__init__('coinbase')
        self.base_url = 'https://api.exchange.coinbase.com'  # Coinbase Advanced API
        self.session = None
        self.rate_limit_delay = 0.1  # 10 requests per second
        self.last_request_time = 0
        
        # Symbol mapping from common formats to Coinbase product IDs
        self.symbol_map = {
            'BTC-USDT': 'BTC-USD',
            'BTC/USDT': 'BTC-USD',
            'BTCUSDT': 'BTC-USD',
            'BTC': 'BTC-USD',
            'BTC-USD': 'BTC-USD',
            'BTC/USD': 'BTC-USD',
            'BTCUSD': 'BTC-USD',
            'ETH-USDT': 'ETH-USD',
            'ETH/USDT': 'ETH-USD',
            'ETHUSDT': 'ETH-USD',
            'ETH': 'ETH-USD',
            'ETH-USD': 'ETH-USD',
            'ETH/USD': 'ETH-USD',
            'ETHUSD': 'ETH-USD',
            'LTC-USDT': 'LTC-USD',
            'LTC/USDT': 'LTC-USD',
            'LTCUSDT': 'LTC-USD',
            'LTC': 'LTC-USD',
            'LTC-USD': 'LTC-USD',
            'LTC/USD': 'LTC-USD',
            'LTCUSD': 'LTC-USD',
            'BCH-USDT': 'BCH-USD',
            'BCH/USDT': 'BCH-USD',
            'BCHUSDT': 'BCH-USD',
            'BCH': 'BCH-USD',
            'BCH-USD': 'BCH-USD',
            'BCH/USD': 'BCH-USD',
            'BCHUSD': 'BCH-USD',
            'ADA-USDT': 'ADA-USD',
            'ADA/USDT': 'ADA-USD',
            'ADAUSDT': 'ADA-USD',
            'ADA': 'ADA-USD',
            'ADA-USD': 'ADA-USD',
            'ADA/USD': 'ADA-USD',
            'ADAUSD': 'ADA-USD',
            'DOT-USDT': 'DOT-USD',
            'DOT/USDT': 'DOT-USD',
            'DOTUSDT': 'DOT-USD',
            'DOT': 'DOT-USD',
            'DOT-USD': 'DOT-USD',
            'DOT/USD': 'DOT-USD',
            'DOTUSD': 'DOT-USD',
            'LINK-USDT': 'LINK-USD',
            'LINK/USDT': 'LINK-USD',
            'LINKUSDT': 'LINK-USD',
            'LINK': 'LINK-USD',
            'LINK-USD': 'LINK-USD',
            'LINK/USD': 'LINK-USD',
            'LINKUSD': 'LINK-USD',
            'ATOM-USDT': 'ATOM-USD',
            'ATOM/USDT': 'ATOM-USD',
            'ATOMUSDT': 'ATOM-USD',
            'ATOM': 'ATOM-USD',
            'ATOM-USD': 'ATOM-USD',
            'ATOM/USD': 'ATOM-USD',
            'ATOMUSD': 'ATOM-USD'
        }
        
        # Coinbase granularity mapping (in seconds)
        self.granularity_map = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '1h': 3600,
            '6h': 21600,
            '1d': 86400
        }
    
    async def connect(self) -> bool:
        """Connect to Coinbase API"""
        try:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'Analytical-Punch/1.0',
                    'Accept': 'application/json'
                }
            )
            
            # Test connection by fetching server time
            await self._rate_limit()
            async with self.session.get(f'{self.base_url}/time') as response:
                if response.status == 200:
                    data = await response.json()
                    if 'iso' in data:
                        self.connected = True
                        logger.info("Coinbase API connected successfully")
                        return True
                    else:
                        logger.error("Coinbase API returned invalid time response")
                        return False
                else:
                    logger.error(f"Coinbase API connection failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to connect to Coinbase API: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Coinbase API"""
        if self.session:
            await self.session.close()
            self.session = None
        self.connected = False
        logger.info("Coinbase API disconnected")
    
    async def _rate_limit(self):
        """Implement rate limiting"""
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    def _get_coinbase_product(self, symbol: str) -> str:
        """Convert symbol to Coinbase product ID"""
        symbol = symbol.upper()
        return self.symbol_map.get(symbol, symbol.replace('/', '-'))
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1h',
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = 500
    ) -> pd.DataFrame:
        """Fetch OHLCV data from Coinbase"""
        if not self.session:
            raise RuntimeError("Not connected to Coinbase API")
        
        product_id = self._get_coinbase_product(symbol)
        granularity = self.granularity_map.get(timeframe, 3600)
        
        # Calculate time range
        if not end_time:
            end_time = datetime.utcnow()
        if not start_time:
            # Calculate start time based on limit and granularity
            delta_seconds = limit * granularity
            start_time = end_time - timedelta(seconds=delta_seconds)
        
        await self._rate_limit()
        
        url = f'{self.base_url}/products/{product_id}/candles'
        params = {
            'start': start_time.isoformat() + 'Z',
            'end': end_time.isoformat() + 'Z',
            'granularity': granularity
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Coinbase API error {response.status}: {text}")
                
                data = await response.json()
                
                if not isinstance(data, list):
                    raise Exception(f"Unexpected response format from Coinbase: {type(data)}")
                
                if not data:
                    raise Exception(f"No candle data returned for {product_id}")
                
                # Convert to DataFrame
                # Coinbase returns: [timestamp, low, high, open, close, volume]
                df_data = []
                for candle in reversed(data):  # Coinbase returns newest first, we want oldest first
                    if len(candle) >= 6:
                        timestamp = datetime.fromtimestamp(candle[0])
                        df_data.append({
                            'timestamp': timestamp,
                            'open': float(candle[3]),
                            'high': float(candle[2]),
                            'low': float(candle[1]),
                            'close': float(candle[4]),
                            'volume': float(candle[5])
                        })
                
                if not df_data:
                    raise Exception(f"No valid candle data for {product_id}")
                
                df = pd.DataFrame(df_data)
                df.set_index('timestamp', inplace=True)
                df.index = pd.to_datetime(df.index)
                
                # Limit to requested number of candles
                df = df.tail(limit).copy()
                
                return df
                
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol} from Coinbase: {e}")
            raise
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker data from Coinbase"""
        if not self.session:
            raise RuntimeError("Not connected to Coinbase API")
        
        product_id = self._get_coinbase_product(symbol)
        
        await self._rate_limit()
        
        # Fetch ticker data
        ticker_url = f'{self.base_url}/products/{product_id}/ticker'
        stats_url = f'{self.base_url}/products/{product_id}/stats'
        
        try:
            # Fetch both ticker and 24h stats
            async with self.session.get(ticker_url) as ticker_response:
                if ticker_response.status != 200:
                    text = await ticker_response.text()
                    raise Exception(f"Coinbase ticker API error {ticker_response.status}: {text}")
                
                ticker_data = await ticker_response.json()
            
            await self._rate_limit()  # Rate limit between requests
            
            async with self.session.get(stats_url) as stats_response:
                if stats_response.status != 200:
                    # Stats might not be available, use ticker data only
                    stats_data = {}
                else:
                    stats_data = await stats_response.json()
            
            # Parse ticker data
            last_price = float(ticker_data.get('price', 0))
            bid_price = float(ticker_data.get('bid', last_price * 0.9995))
            ask_price = float(ticker_data.get('ask', last_price * 1.0005))
            volume_24h = float(ticker_data.get('volume', 0))
            
            # Parse 24h stats if available
            high_24h = float(stats_data.get('high', last_price))
            low_24h = float(stats_data.get('low', last_price))
            open_24h = float(stats_data.get('open', last_price))
            
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
            
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol} from Coinbase: {e}")
            raise
    
    async def fetch_order_book(self, symbol: str, level: int = 2) -> Dict[str, Any]:
        """Fetch order book data from Coinbase"""
        if not self.session:
            raise RuntimeError("Not connected to Coinbase API")
        
        product_id = self._get_coinbase_product(symbol)
        
        await self._rate_limit()
        
        url = f'{self.base_url}/products/{product_id}/book'
        params = {'level': level}  # Level 2 gives aggregated order book
        
        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"Coinbase API error {response.status}: {text}")
            
            data = await response.json()
            
            if 'bids' not in data or 'asks' not in data:
                raise Exception("Invalid order book response from Coinbase")
            
            # Convert to standardized format
            bids = [[float(bid[0]), float(bid[1])] for bid in data['bids']]
            asks = [[float(ask[0]), float(ask[1])] for ask in data['asks']]
            
            return {
                'symbol': symbol,
                'bids': bids,
                'asks': asks,
                'timestamp': int(time.time() * 1000)
            }
    
    async def get_symbols(self) -> List[str]:
        """Get available trading pairs from Coinbase"""
        if not self.session:
            await self.connect()
        
        await self._rate_limit()
        
        url = f'{self.base_url}/products'
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return list(self.symbol_map.keys())  # Fallback to our mapped symbols
                
                data = await response.json()
                
                if not isinstance(data, list):
                    return list(self.symbol_map.keys())
                
                # Extract USD pairs from Coinbase response
                symbols = []
                for product in data:
                    if (isinstance(product, dict) and 
                        product.get('quote_currency') == 'USD' and 
                        product.get('status') == 'online'):
                        
                        product_id = product.get('id', '')
                        base_currency = product.get('base_currency', '')
                        
                        if base_currency and product_id:
                            # Add various format variations
                            symbols.extend([
                                product_id,  # BTC-USD
                                product_id.replace('-', '/'),  # BTC/USD
                                product_id.replace('-', ''),   # BTCUSD
                                f"{base_currency}-USDT",       # BTC-USDT
                                f"{base_currency}/USDT",       # BTC/USDT
                                f"{base_currency}USDT",        # BTCUSDT
                                base_currency                  # BTC
                            ])
                
                # Combine with our predefined symbols
                all_symbols = list(set(symbols + list(self.symbol_map.keys())))
                return sorted(all_symbols)
                
        except Exception as e:
            logger.error(f"Error fetching symbols from Coinbase: {e}")
            return list(self.symbol_map.keys())
    
    def is_symbol_valid(self, symbol: str) -> bool:
        """Check if symbol is valid for Coinbase"""
        symbol = symbol.upper()
        return symbol in self.symbol_map or any(
            currency in symbol for currency in ['USD', 'USDT']
        )
    
    async def get_server_time(self) -> Dict[str, Any]:
        """Get Coinbase server time"""
        if not self.session:
            raise RuntimeError("Not connected to Coinbase API")
        
        await self._rate_limit()
        
        url = f'{self.base_url}/time'
        
        async with self.session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Coinbase API error {response.status}")
            
            return await response.json()
    
    async def get_currencies(self) -> List[Dict[str, Any]]:
        """Get list of supported currencies"""
        if not self.session:
            raise RuntimeError("Not connected to Coinbase API")
        
        await self._rate_limit()
        
        url = f'{self.base_url}/currencies'
        
        async with self.session.get(url) as response:
            if response.status != 200:
                return []
            
            return await response.json()