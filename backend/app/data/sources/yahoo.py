import yfinance as yf
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.data.sources.base import DataSource, Timeframe
from app.utils.cache import cached

# Thread pool for blocking yfinance calls
executor = ThreadPoolExecutor(max_workers=5)


class YahooDataSource(DataSource):
    """Yahoo Finance data source for stocks and ETFs"""
    
    def __init__(self):
        super().__init__("yahoo")
        self._symbols_cache = None
        self._popular_symbols = [
            # Major indices
            "^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX",
            # Major stocks
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA",
            "JPM", "V", "JNJ", "WMT", "PG", "UNH", "HD", "MA",
            # ETFs
            "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "EEM", "GLD",
            # Crypto ETFs
            "BITO", "BTF", "XBTF"
        ]
    
    async def connect(self) -> bool:
        """Connect to Yahoo Finance (no authentication needed)"""
        try:
            # Test connection by fetching a known symbol
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(executor, yf.Ticker, "AAPL")
            info = await loop.run_in_executor(executor, lambda: ticker.info)
            
            if info:
                self._connected = True
                self.logger.info("Connected to Yahoo Finance")
                return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Yahoo Finance: {e}")
            self._connected = False
            
        return False
    
    async def disconnect(self):
        """Disconnect from Yahoo Finance"""
        self._connected = False
    
    @cached(prefix="yahoo_ohlcv", ttl=300)  # 5 minute cache
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """Fetch OHLCV data from Yahoo Finance"""
        try:
            # Validate timeframe
            if not self._validate_timeframe(timeframe):
                raise ValueError(f"Invalid timeframe: {timeframe}")
            
            # Convert timeframe to Yahoo format
            interval = self._convert_timeframe(timeframe)
            
            # Set default date range
            if not end_time:
                end_time = datetime.now()
            
            if not start_time:
                # Calculate based on timeframe and limit
                if limit:
                    minutes = Timeframe.to_minutes(timeframe)
                    start_time = end_time - timedelta(minutes=minutes * limit)
                else:
                    # Default to 90 days for daily, 5 days for intraday
                    if timeframe in ["1d", "1w", "1M"]:
                        start_time = end_time - timedelta(days=90)
                    else:
                        start_time = end_time - timedelta(days=5)
            
            # Fetch data in thread pool
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(executor, yf.Ticker, symbol)
            
            df = await loop.run_in_executor(
                executor,
                ticker.history,
                start=start_time,
                end=end_time,
                interval=interval,
                auto_adjust=True,
                prepost=True
            )
            
            if df.empty:
                raise ValueError(f"No data available for {symbol}")
            
            # Rename columns to match standard format
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Select only OHLCV columns
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            # Apply limit if specified
            if limit and len(df) > limit:
                df = df.iloc[-limit:]
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching OHLCV from Yahoo: {e}")
            raise
    
    async def fetch_ticker(self, symbol: str) -> Dict:
        """Fetch current ticker data"""
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(executor, yf.Ticker, symbol)
            info = await loop.run_in_executor(executor, lambda: ticker.info)
            
            # Get current price
            current_price = info.get('regularMarketPrice', info.get('price', 0))
            prev_close = info.get('previousClose', 0)
            
            return {
                'bid': info.get('bid', current_price),
                'ask': info.get('ask', current_price),
                'last': current_price,
                'volume_24h': info.get('volume', 0),
                'change_24h': current_price - prev_close if prev_close else 0,
                'change_24h_pct': ((current_price - prev_close) / prev_close * 100) if prev_close else 0,
                'high_24h': info.get('dayHigh', 0),
                'low_24h': info.get('dayLow', 0),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'timestamp': int(datetime.now().timestamp() * 1000)
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching ticker from Yahoo: {e}")
            raise
    
    async def get_symbols(self) -> List[str]:
        """Get list of popular symbols (Yahoo doesn't provide full list)"""
        # Return cached popular symbols
        return self._popular_symbols
    
    def is_symbol_valid(self, symbol: str) -> bool:
        """Check if symbol is valid by trying to fetch its info"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return bool(info and 'symbol' in info)
        except:
            return False
    
    def _convert_timeframe(self, timeframe: str) -> str:
        """Convert our timeframe to Yahoo format"""
        mapping = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "60m",  # Yahoo uses 60m instead of 1h
            "1d": "1d",
            "1w": "1wk",  # Yahoo uses 1wk instead of 1w
            "1M": "1mo"   # Yahoo uses 1mo instead of 1M
        }
        
        # Yahoo doesn't support 4h timeframe
        if timeframe == "4h":
            raise ValueError("Yahoo Finance doesn't support 4h timeframe")
        
        return mapping.get(timeframe, "1d")
    
    async def fetch_company_info(self, symbol: str) -> Dict:
        """Fetch additional company information"""
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(executor, yf.Ticker, symbol)
            info = await loop.run_in_executor(executor, lambda: ticker.info)
            
            return {
                'name': info.get('longName', ''),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'description': info.get('longBusinessSummary', ''),
                'website': info.get('website', ''),
                'employees': info.get('fullTimeEmployees', 0),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'dividend_yield': info.get('dividendYield', 0),
                '52_week_high': info.get('fiftyTwoWeekHigh', 0),
                '52_week_low': info.get('fiftyTwoWeekLow', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching company info from Yahoo: {e}")
            return {}