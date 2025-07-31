from typing import Dict, List, Optional, Type
from datetime import datetime
import pandas as pd

from app.data.sources.base import DataSource
from app.data.sources.binance import BinanceDataSource
from app.data.sources.yahoo import YahooDataSource
from app.data.sources.csv_source import CSVDataSource
from app.config import get_config
from app.utils.logger import setup_logger

config = get_config()
logger = setup_logger(__name__)


class DataManager:
    """
    Manages multiple data sources and provides unified interface
    """
    
    def __init__(self):
        self.sources: Dict[str, DataSource] = {}
        self._initialized = False
        
    async def initialize(self):
        """Initialize all available data sources"""
        if self._initialized:
            return
        
        # Initialize sources based on configuration
        source_classes = {
            'binance': BinanceDataSource,
            'yahoo': YahooDataSource,
            'csv': CSVDataSource
        }
        
        for source_name in config.AVAILABLE_SOURCES:
            if source_name in source_classes:
                try:
                    source = source_classes[source_name]()
                    if await source.connect():
                        self.sources[source_name] = source
                        logger.info(f"Initialized {source_name} data source")
                except Exception as e:
                    logger.error(f"Failed to initialize {source_name}: {e}")
        
        self._initialized = True
        logger.info(f"Data manager initialized with {len(self.sources)} sources")
    
    async def shutdown(self):
        """Shutdown all data sources"""
        for source in self.sources.values():
            await source.disconnect()
        self.sources.clear()
        self._initialized = False
    
    def get_source(self, symbol: str) -> Optional[DataSource]:
        """
        Determine the appropriate data source for a symbol
        
        Priority:
        1. CSV (if file exists)
        2. Binance (for crypto)
        3. Yahoo (for stocks)
        """
        symbol = symbol.upper()
        
        # Check CSV first (for backtesting)
        if 'csv' in self.sources:
            if self.sources['csv'].is_symbol_valid(symbol):
                return self.sources['csv']
        
        # Check if it's a crypto symbol
        if self._is_crypto_symbol(symbol):
            if 'binance' in self.sources:
                return self.sources['binance']
        
        # Default to Yahoo for stocks
        if 'yahoo' in self.sources:
            return self.sources['yahoo']
        
        # Fallback to first available source
        if self.sources:
            return list(self.sources.values())[0]
        
        return None
    
    def _is_crypto_symbol(self, symbol: str) -> bool:
        """Determine if symbol is cryptocurrency"""
        # Common crypto quote currencies
        crypto_quotes = ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB', 'USDC']
        
        # Check for slash notation
        if '/' in symbol:
            quote = symbol.split('/')[1]
            return quote in crypto_quotes
        
        # Check suffix
        for quote in crypto_quotes:
            if symbol.endswith(quote):
                return True
        
        return False
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        source_name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from appropriate source
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
            start_time: Start time for historical data
            end_time: End time for historical data
            limit: Maximum number of candles
            source_name: Force specific source (optional)
        """
        if not self._initialized:
            await self.initialize()
        
        # Get appropriate source
        if source_name and source_name in self.sources:
            source = self.sources[source_name]
        else:
            source = self.get_source(symbol)
        
        if not source:
            raise ValueError(f"No data source available for {symbol}")
        
        try:
            df = await source.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
            
            # Add source metadata
            df.attrs['source'] = source.name
            df.attrs['symbol'] = symbol
            df.attrs['timeframe'] = timeframe
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol} from {source.name}: {e}")
            
            # Try fallback sources
            for fallback_name, fallback_source in self.sources.items():
                if fallback_name != source.name:
                    try:
                        logger.info(f"Trying fallback source {fallback_name}")
                        df = await fallback_source.fetch_ohlcv(
                            symbol=symbol,
                            timeframe=timeframe,
                            start_time=start_time,
                            end_time=end_time,
                            limit=limit
                        )
                        df.attrs['source'] = fallback_name
                        df.attrs['symbol'] = symbol
                        df.attrs['timeframe'] = timeframe
                        return df
                    except:
                        continue
            
            raise
    
    async def fetch_ticker(
        self,
        symbol: str,
        source_name: Optional[str] = None
    ) -> Dict:
        """Fetch current ticker data"""
        if not self._initialized:
            await self.initialize()
        
        # Get appropriate source
        if source_name and source_name in self.sources:
            source = self.sources[source_name]
        else:
            source = self.get_source(symbol)
        
        if not source:
            raise ValueError(f"No data source available for {symbol}")
        
        ticker = await source.fetch_ticker(symbol)
        ticker['source'] = source.name
        
        return ticker
    
    async def get_available_symbols(self) -> Dict[str, List[str]]:
        """Get available symbols from all sources"""
        if not self._initialized:
            await self.initialize()
        
        symbols = {}
        
        for source_name, source in self.sources.items():
            try:
                source_symbols = await source.get_symbols()
                symbols[source_name] = source_symbols
            except Exception as e:
                logger.error(f"Error getting symbols from {source_name}: {e}")
                symbols[source_name] = []
        
        return symbols
    
    async def validate_symbol(self, symbol: str) -> Dict[str, bool]:
        """Check symbol validity across all sources"""
        if not self._initialized:
            await self.initialize()
        
        results = {}
        
        for source_name, source in self.sources.items():
            try:
                results[source_name] = source.is_symbol_valid(symbol)
            except:
                results[source_name] = False
        
        return results
    
    async def fetch_multi_timeframe(
        self,
        symbol: str,
        timeframes: List[str],
        limit: int = 100
    ) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple timeframes"""
        results = {}
        
        source = self.get_source(symbol)
        if not source:
            raise ValueError(f"No data source available for {symbol}")
        
        for timeframe in timeframes:
            try:
                df = await source.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=limit
                )
                results[timeframe] = df
            except Exception as e:
                logger.error(f"Error fetching {timeframe} data: {e}")
                results[timeframe] = pd.DataFrame()
        
        return results


# Global data manager instance
data_manager = DataManager()