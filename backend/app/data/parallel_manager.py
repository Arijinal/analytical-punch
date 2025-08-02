"""
Parallel data manager for faster data fetching from multiple sources.
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

from app.data.manager import DataManager
from app.utils.logger import setup_logger
from app.utils.symbol_normalizer import symbol_normalizer

logger = setup_logger(__name__)


class ParallelDataManager(DataManager):
    """Enhanced data manager with parallel source queries for faster loading."""
    
    def __init__(self):
        super().__init__()
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    async def fetch_ohlcv_parallel(
        self,
        symbol: str,
        timeframe: str = '1h',
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        source_name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from multiple sources in parallel and return the fastest result.
        """
        if not self._initialized:
            await self.initialize()
        
        # Normalize symbol format
        normalized_symbol = symbol_normalizer.normalize_symbol(symbol)
        logger.info(f"Parallel fetch for {normalized_symbol}")
        
        # If specific source requested, use normal fetch
        if source_name:
            return await self.fetch_ohlcv(
                symbol, timeframe, start_time, end_time, limit, source_name
            )
        
        # Get compatible sources for this symbol
        compatible_sources = []
        for source_name, source in self.sources.items():
            source_symbol = symbol_normalizer.convert_for_source(normalized_symbol, source_name)
            if source_symbol and source.is_symbol_valid(source_symbol):
                compatible_sources.append((source_name, source, source_symbol))
        
        if not compatible_sources:
            raise ValueError(f"No compatible sources for {symbol}")
        
        # Create tasks for parallel fetching
        tasks = []
        for source_name, source, source_symbol in compatible_sources:
            task = self._fetch_with_timeout(
                source, source_symbol, timeframe, 
                start_time, end_time, limit, source_name
            )
            tasks.append(task)
        
        # Wait for the first successful result
        for coro in asyncio.as_completed(tasks):
            try:
                result, source_name = await coro
                if result is not None and not result.empty:
                    logger.info(f"Successfully fetched data from {source_name} (first to complete)")
                    
                    # Cancel remaining tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    
                    # Add metadata
                    result.attrs['source'] = source_name
                    result.attrs['symbol'] = symbol
                    result.attrs['normalized_symbol'] = normalized_symbol
                    result.attrs['timeframe'] = timeframe
                    
                    return result
            except Exception as e:
                logger.debug(f"Source failed: {e}")
                continue
        
        # If all sources failed, fall back to sequential fetch
        logger.warning("All parallel fetches failed, falling back to sequential")
        return await self.fetch_ohlcv(symbol, timeframe, start_time, end_time, limit)
    
    async def _fetch_with_timeout(
        self,
        source: Any,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        limit: Optional[int],
        source_name: str,
        timeout: float = 5.0
    ) -> tuple[pd.DataFrame, str]:
        """Fetch data from a source with timeout."""
        try:
            result = await asyncio.wait_for(
                source.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit
                ),
                timeout=timeout
            )
            return result, source_name
        except asyncio.TimeoutError:
            logger.warning(f"{source_name} timed out after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"{source_name} error: {e}")
            raise
    
    async def warmup_cache(self, symbols: List[str], timeframes: List[str] = ['1h', '1d']):
        """Pre-fetch data for common symbols to warm up the cache."""
        logger.info(f"Warming up cache for {len(symbols)} symbols")
        
        tasks = []
        for symbol in symbols:
            for timeframe in timeframes:
                task = self.fetch_ohlcv_parallel(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=100  # Just recent data for cache
                )
                tasks.append(task)
        
        # Execute warmup in batches to avoid overwhelming sources
        batch_size = 5
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            try:
                await asyncio.gather(*batch, return_exceptions=True)
            except Exception as e:
                logger.warning(f"Cache warmup batch failed: {e}")
        
        logger.info("Cache warmup completed")


# Create singleton instance
parallel_data_manager = ParallelDataManager()