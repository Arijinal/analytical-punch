from typing import Dict, List, Optional, Type
from datetime import datetime
import pandas as pd

from app.data.sources.base import DataSource
from app.data.sources.binance import BinanceDataSource
from app.data.sources.yahoo import YahooDataSource
from app.data.sources.csv_source import CSVDataSource
from app.data.sources.coingecko import CoinGeckoDataSource
from app.data.sources.kraken import KrakenDataSource
from app.data.sources.coinbase import CoinbaseDataSource
from app.config import get_config
from app.utils.logger import setup_logger
from app.utils.symbol_normalizer import symbol_normalizer

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
        # Prioritize working sources: CoinGecko (free, reliable), Kraken (exchange), Coinbase (exchange)
        source_classes = {
            'coingecko': CoinGeckoDataSource,
            'kraken': KrakenDataSource,
            'coinbase': CoinbaseDataSource,
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
        1. CSV (if file exists - for backtesting)
        2. CoinGecko (for crypto - free, reliable)
        3. Kraken (for crypto - exchange data)
        4. Coinbase (for crypto - exchange data)
        5. Binance (for crypto - if available)
        6. Yahoo (for stocks)
        """
        # Use symbol normalizer to determine symbol type and compatible sources
        compatible_sources = symbol_normalizer.get_compatible_sources(symbol)
        is_crypto = symbol_normalizer.is_crypto_symbol(symbol)
        is_stock = symbol_normalizer.is_stock_symbol(symbol)
        
        logger.info(f"Symbol {symbol}: crypto={is_crypto}, stock={is_stock}, compatible={compatible_sources}")
        
        # Check CSV first (for backtesting)
        if 'csv' in self.sources:
            csv_symbol = symbol_normalizer.convert_for_source(symbol, 'csv')
            if self.sources['csv'].is_symbol_valid(csv_symbol):
                return self.sources['csv']
        
        # For crypto symbols, try crypto sources in order
        if is_crypto:
            crypto_priority = ['coingecko', 'kraken', 'coinbase', 'binance']
            for source_name in crypto_priority:
                if source_name in self.sources and source_name in compatible_sources:
                    source = self.sources[source_name]
                    source_symbol = symbol_normalizer.convert_for_source(symbol, source_name)
                    if source.is_symbol_valid(source_symbol):
                        logger.info(f"Selected {source_name} for crypto symbol {symbol}")
                        return source
        
        # For stock symbols, try Yahoo first
        if is_stock and 'yahoo' in self.sources:
            yahoo_symbol = symbol_normalizer.convert_for_source(symbol, 'yahoo')
            if self.sources['yahoo'].is_symbol_valid(yahoo_symbol):
                logger.info(f"Selected yahoo for stock symbol {symbol}")
                return self.sources['yahoo']
        
        # Final fallback - try any compatible source
        for source_name in compatible_sources:
            if source_name in self.sources:
                source = self.sources[source_name]
                source_symbol = symbol_normalizer.convert_for_source(symbol, source_name)
                if source.is_symbol_valid(source_symbol):
                    logger.info(f"Selected fallback {source_name} for symbol {symbol}")
                    return source
        
        logger.warning(f"No compatible data source found for symbol {symbol}")
        return None
    
    def _is_crypto_symbol(self, symbol: str) -> bool:
        """Determine if symbol is cryptocurrency"""
        # Common crypto quote currencies and patterns
        crypto_quotes = ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB', 'USDC', 'USD']
        crypto_bases = ['BTC', 'ETH', 'LTC', 'BCH', 'ADA', 'DOT', 'LINK', 'SOL', 'AVAX', 'MATIC', 'UNI', 'ATOM']
        
        # Check for slash notation (BTC/USD, ETH/USDT)
        if '/' in symbol:
            base, quote = symbol.split('/', 1)
            return base in crypto_bases or quote in crypto_quotes
        
        # Check for dash notation (BTC-USD, ETH-USDT)
        if '-' in symbol:
            base, quote = symbol.split('-', 1)
            return base in crypto_bases or quote in crypto_quotes
        
        # Check suffix (BTCUSD, ETHUSDT)
        for quote in crypto_quotes:
            if symbol.endswith(quote) and len(symbol) > len(quote):
                potential_base = symbol[:-len(quote)]
                if potential_base in crypto_bases:
                    return True
        
        # Check if it's a known crypto base currency
        if symbol in crypto_bases:
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
            symbol: Trading symbol (any format - will be normalized)
            timeframe: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
            start_time: Start time for historical data
            end_time: End time for historical data
            limit: Maximum number of candles
            source_name: Force specific source (optional)
        """
        if not self._initialized:
            await self.initialize()
        
        # Normalize symbol format
        normalized_symbol = symbol_normalizer.normalize_symbol(symbol)
        logger.info(f"Normalized symbol {symbol} -> {normalized_symbol}")
        
        # Get appropriate source
        if source_name and source_name in self.sources:
            source = self.sources[source_name]
        else:
            source = self.get_source(normalized_symbol)
        
        if not source:
            raise ValueError(f"No data source available for {symbol} (normalized: {normalized_symbol})")
        
        # Convert symbol to source-specific format
        source_symbol = symbol_normalizer.convert_for_source(normalized_symbol, source.name)
        logger.info(f"Converting {normalized_symbol} to {source_symbol} for {source.name}")
        
        try:
            df = await source.fetch_ohlcv(
                symbol=source_symbol,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
            
            # Add source metadata
            df.attrs['source'] = source.name
            df.attrs['symbol'] = symbol  # Keep original symbol for frontend
            df.attrs['normalized_symbol'] = normalized_symbol
            df.attrs['source_symbol'] = source_symbol
            df.attrs['timeframe'] = timeframe
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol} ({source_symbol}) from {source.name}: {e}")
            
            # Try fallback sources in priority order
            fallback_priority = ['coingecko', 'kraken', 'coinbase', 'binance', 'yahoo', 'csv']
            
            for fallback_name in fallback_priority:
                if fallback_name != source.name and fallback_name in self.sources:
                    fallback_source = self.sources[fallback_name]
                    try:
                        logger.info(f"Trying fallback source {fallback_name} for {symbol}")
                        
                        # Check if fallback source supports this symbol
                        if not fallback_source.is_symbol_valid(symbol):
                            continue
                        
                        # Convert symbol for fallback source
                        fallback_symbol = symbol_normalizer.convert_for_source(normalized_symbol, fallback_name)
                        logger.info(f"Trying fallback {fallback_name} with symbol {fallback_symbol}")
                        
                        df = await fallback_source.fetch_ohlcv(
                            symbol=fallback_symbol,
                            timeframe=timeframe,
                            start_time=start_time,
                            end_time=end_time,
                            limit=limit
                        )
                        df.attrs['source'] = fallback_name
                        df.attrs['symbol'] = symbol  # Keep original symbol
                        df.attrs['normalized_symbol'] = normalized_symbol
                        df.attrs['source_symbol'] = fallback_symbol
                        df.attrs['timeframe'] = timeframe
                        logger.info(f"Successfully fetched data from fallback source {fallback_name}")
                        return df
                    except Exception as fallback_error:
                        logger.warning(f"Fallback source {fallback_name} also failed: {fallback_error}")
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
        
        # Normalize symbol format
        normalized_symbol = symbol_normalizer.normalize_symbol(symbol)
        
        # Get appropriate source
        if source_name and source_name in self.sources:
            source = self.sources[source_name]
        else:
            source = self.get_source(normalized_symbol)
        
        if not source:
            raise ValueError(f"No data source available for {symbol} (normalized: {normalized_symbol})")
        
        # Convert symbol to source-specific format
        source_symbol = symbol_normalizer.convert_for_source(normalized_symbol, source.name)
        
        try:
            ticker = await source.fetch_ticker(source_symbol)
            ticker['source'] = source.name
            ticker['symbol'] = symbol  # Keep original symbol for frontend
            ticker['normalized_symbol'] = normalized_symbol
            return ticker
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol} ({source_symbol}) from {source.name}: {e}")
            
            # Try fallback sources for ticker data
            fallback_priority = ['coingecko', 'kraken', 'coinbase', 'binance', 'yahoo']
            
            for fallback_name in fallback_priority:
                if fallback_name != source.name and fallback_name in self.sources:
                    fallback_source = self.sources[fallback_name]
                    try:
                        # Convert symbol for fallback source
                        fallback_symbol = symbol_normalizer.convert_for_source(normalized_symbol, fallback_name)
                        if fallback_source.is_symbol_valid(fallback_symbol):
                            logger.info(f"Trying fallback ticker source {fallback_name} for {symbol} ({fallback_symbol})")
                            ticker = await fallback_source.fetch_ticker(fallback_symbol)
                            ticker['source'] = fallback_name
                            ticker['symbol'] = symbol  # Keep original symbol
                            ticker['normalized_symbol'] = normalized_symbol
                            return ticker
                    except Exception as fallback_error:
                        logger.warning(f"Fallback ticker source {fallback_name} failed: {fallback_error}")
                        continue
            
            raise
    
    async def get_available_symbols(self) -> Dict[str, List[str]]:
        """Get available symbols from all sources"""
        if not self._initialized:
            await self.initialize()
        
        symbols = {}
        
        # Get symbols from sources in priority order
        source_priority = ['coingecko', 'kraken', 'coinbase', 'binance', 'yahoo', 'csv']
        
        for source_name in source_priority:
            if source_name in self.sources:
                try:
                    source_symbols = await self.sources[source_name].get_symbols()
                    symbols[source_name] = source_symbols
                    logger.info(f"Retrieved {len(source_symbols)} symbols from {source_name}")
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