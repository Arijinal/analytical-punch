import ccxt
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import asyncio

from app.data.sources.base import DataSource, Timeframe
from app.config import get_config
from app.utils.cache import cached

config = get_config()


class BinanceDataSource(DataSource):
    """Binance data source using CCXT"""
    
    def __init__(self):
        super().__init__("binance")
        self.exchange = None
        self._symbols_cache = None
        self._last_symbols_update = None
    
    async def connect(self) -> bool:
        """Connect to Binance"""
        try:
            # Initialize CCXT exchange
            exchange_config = {
                'enableRateLimit': True,
                'rateLimit': 50,  # 50ms between requests
                'options': {
                    'defaultType': 'spot',
                }
            }
            
            # Add API credentials if available
            if config.BINANCE_API_KEY and config.BINANCE_API_SECRET:
                exchange_config.update({
                    'apiKey': config.BINANCE_API_KEY,
                    'secret': config.BINANCE_API_SECRET,
                })
            
            self.exchange = ccxt.binance(exchange_config)
            
            # Test connection
            await self.exchange.load_markets()
            self._connected = True
            self.logger.info("Connected to Binance")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Binance: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Binance"""
        if self.exchange:
            await self.exchange.close()
        self._connected = False
    
    @cached(prefix="binance_ohlcv", ttl=300)  # 5 minute cache
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """Fetch OHLCV data from Binance"""
        if not self._connected:
            await self.connect()
        
        try:
            # Validate timeframe
            if not self._validate_timeframe(timeframe):
                raise ValueError(f"Invalid timeframe: {timeframe}")
            
            # Convert symbol format (BTC/USDT)
            symbol = self.standardize_symbol(symbol)
            
            # Calculate limit if not provided
            if limit is None:
                if start_time and end_time:
                    minutes = Timeframe.to_minutes(timeframe)
                    limit = int((end_time - start_time).total_seconds() / 60 / minutes)
                else:
                    limit = 500  # Default
            
            # Binance max limit is 1000
            limit = min(limit, 1000)
            
            # Convert start_time to milliseconds
            since = None
            if start_time:
                since = int(start_time.timestamp() * 1000)
            
            # Fetch data
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol,
                timeframe,
                since=since,
                limit=limit
            )
            
            # Convert to DataFrame
            df = self._prepare_dataframe(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Filter by end_time if provided
            if end_time:
                df = df[df.index <= end_time]
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching OHLCV from Binance: {e}")
            raise
    
    async def fetch_ticker(self, symbol: str) -> Dict:
        """Fetch current ticker data"""
        if not self._connected:
            await self.connect()
        
        try:
            symbol = self.standardize_symbol(symbol)
            ticker = await self.exchange.fetch_ticker(symbol)
            
            return {
                'bid': ticker.get('bid', 0),
                'ask': ticker.get('ask', 0),
                'last': ticker.get('last', 0),
                'volume_24h': ticker.get('quoteVolume', 0),
                'change_24h': ticker.get('change', 0),
                'change_24h_pct': ticker.get('percentage', 0),
                'high_24h': ticker.get('high', 0),
                'low_24h': ticker.get('low', 0),
                'timestamp': ticker.get('timestamp', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching ticker from Binance: {e}")
            raise
    
    async def get_symbols(self) -> List[str]:
        """Get list of available symbols"""
        if not self._connected:
            await self.connect()
        
        # Cache symbols for 1 hour
        if self._symbols_cache and self._last_symbols_update:
            if datetime.now() - self._last_symbols_update < timedelta(hours=1):
                return self._symbols_cache
        
        try:
            markets = self.exchange.markets
            symbols = []
            
            for symbol, market in markets.items():
                # Only include active spot markets
                if market.get('active', True) and market.get('type') == 'spot':
                    # Filter for major quote currencies
                    if any(quote in symbol for quote in ['/USDT', '/BUSD', '/BTC', '/ETH']):
                        symbols.append(symbol)
            
            self._symbols_cache = sorted(symbols)
            self._last_symbols_update = datetime.now()
            
            return self._symbols_cache
            
        except Exception as e:
            self.logger.error(f"Error fetching symbols from Binance: {e}")
            return []
    
    def is_symbol_valid(self, symbol: str) -> bool:
        """Check if symbol is valid"""
        if not self.exchange or not self.exchange.markets:
            return False
        
        symbol = self.standardize_symbol(symbol)
        return symbol in self.exchange.markets
    
    def standardize_symbol(self, symbol: str) -> str:
        """Standardize symbol format for Binance"""
        symbol = symbol.upper()
        
        # Add slash if missing
        if '/' not in symbol:
            # Try common quote currencies
            for quote in ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB']:
                if symbol.endswith(quote):
                    base = symbol[:-len(quote)]
                    return f"{base}/{quote}"
        
        return symbol
    
    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """Fetch order book data"""
        if not self._connected:
            await self.connect()
        
        try:
            symbol = self.standardize_symbol(symbol)
            order_book = await self.exchange.fetch_order_book(symbol, limit)
            
            return {
                'bids': order_book['bids'][:limit],
                'asks': order_book['asks'][:limit],
                'timestamp': order_book.get('timestamp', 0),
                'symbol': symbol
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching order book from Binance: {e}")
            raise
    
    async def fetch_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Fetch recent trades"""
        if not self._connected:
            await self.connect()
        
        try:
            symbol = self.standardize_symbol(symbol)
            trades = await self.exchange.fetch_trades(symbol, limit=limit)
            
            return [
                {
                    'timestamp': trade['timestamp'],
                    'price': trade['price'],
                    'amount': trade['amount'],
                    'side': trade['side'],
                    'id': trade.get('id', '')
                }
                for trade in trades
            ]
            
        except Exception as e:
            self.logger.error(f"Error fetching trades from Binance: {e}")
            raise