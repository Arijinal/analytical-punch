from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
from enum import Enum

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class Timeframe(Enum):
    """Supported timeframes"""
    ONE_MIN = "1m"
    FIVE_MIN = "5m"
    FIFTEEN_MIN = "15m"
    THIRTY_MIN = "30m"
    ONE_HOUR = "1h"
    FOUR_HOUR = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"
    
    @classmethod
    def to_minutes(cls, timeframe: str) -> int:
        """Convert timeframe to minutes"""
        mapping = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
            "1w": 10080,
            "1M": 43200  # Approximate
        }
        return mapping.get(timeframe, 60)
    
    @classmethod
    def to_pandas_freq(cls, timeframe: str) -> str:
        """Convert to pandas frequency string"""
        mapping = {
            "1m": "1T",
            "5m": "5T",
            "15m": "15T",
            "30m": "30T",
            "1h": "1H",
            "4h": "4H",
            "1d": "1D",
            "1w": "1W",
            "1M": "1M"
        }
        return mapping.get(timeframe, "1H")


class DataSource(ABC):
    """Abstract base class for all data sources"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logger
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to data source"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from data source"""
        pass
    
    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data
        
        Args:
            symbol: Trading symbol (e.g., "BTC/USDT", "AAPL")
            timeframe: Timeframe string (e.g., "1h", "1d")
            start_time: Start time for historical data
            end_time: End time for historical data
            limit: Maximum number of candles to fetch
        
        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index: DatetimeIndex
        """
        pass
    
    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Dict:
        """
        Fetch current ticker data
        
        Returns:
            Dict with: bid, ask, last, volume_24h, change_24h
        """
        pass
    
    @abstractmethod
    async def get_symbols(self) -> List[str]:
        """Get list of available symbols"""
        pass
    
    @abstractmethod
    def is_symbol_valid(self, symbol: str) -> bool:
        """Check if symbol is valid for this source"""
        pass
    
    def standardize_symbol(self, symbol: str) -> str:
        """Standardize symbol format for the source"""
        return symbol.upper()
    
    def _validate_timeframe(self, timeframe: str) -> bool:
        """Validate if timeframe is supported"""
        try:
            Timeframe(timeframe)
            return True
        except ValueError:
            return False
    
    def _prepare_dataframe(self, data: List[List], columns: List[str]) -> pd.DataFrame:
        """
        Prepare standardized DataFrame from raw data
        
        Args:
            data: List of OHLCV data
            columns: Column names
        
        Returns:
            Standardized DataFrame
        """
        df = pd.DataFrame(data, columns=columns)
        
        # Ensure numeric types
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Set datetime index
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
        elif 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
        
        # Sort by time
        df.sort_index(inplace=True)
        
        # Remove duplicates
        df = df[~df.index.duplicated(keep='last')]
        
        return df
    
    def _calculate_metrics(self, df: pd.DataFrame) -> Dict:
        """Calculate basic metrics from OHLCV data"""
        if df.empty:
            return {}
        
        latest = df.iloc[-1]
        prev_close = df.iloc[-2]['close'] if len(df) > 1 else latest['close']
        
        return {
            'last_price': float(latest['close']),
            'change_24h': float(latest['close'] - prev_close),
            'change_24h_pct': float((latest['close'] - prev_close) / prev_close * 100) if prev_close > 0 else 0,
            'high_24h': float(df['high'].max()),
            'low_24h': float(df['low'].min()),
            'volume_24h': float(df['volume'].sum()),
            'last_update': df.index[-1].isoformat()
        }