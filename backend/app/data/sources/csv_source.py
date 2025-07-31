import os
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import asyncio
from pathlib import Path

from app.data.sources.base import DataSource
from app.config import get_config

config = get_config()


class CSVDataSource(DataSource):
    """CSV file data source for backtesting and custom data"""
    
    def __init__(self, data_directory: str = "./data/csv"):
        super().__init__("csv")
        self.data_directory = Path(data_directory)
        self._available_files = {}
        self._loaded_data = {}
    
    async def connect(self) -> bool:
        """Initialize CSV data source"""
        try:
            # Create directory if it doesn't exist
            self.data_directory.mkdir(parents=True, exist_ok=True)
            
            # Scan for available CSV files
            await self._scan_files()
            
            self._connected = True
            self.logger.info(f"CSV data source initialized with {len(self._available_files)} files")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize CSV data source: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """Cleanup CSV data source"""
        self._loaded_data.clear()
        self._connected = False
    
    async def _scan_files(self):
        """Scan directory for CSV files"""
        self._available_files.clear()
        
        for file_path in self.data_directory.glob("**/*.csv"):
            try:
                # Get symbol from filename (without extension)
                symbol = file_path.stem.upper()
                
                # Store file info
                self._available_files[symbol] = {
                    'path': file_path,
                    'size': file_path.stat().st_size,
                    'modified': datetime.fromtimestamp(file_path.stat().st_mtime)
                }
                
            except Exception as e:
                self.logger.warning(f"Error scanning file {file_path}: {e}")
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """Fetch OHLCV data from CSV file"""
        symbol = symbol.upper()
        
        # Check if file exists
        if symbol not in self._available_files:
            raise ValueError(f"No CSV file found for symbol {symbol}")
        
        # Load data if not cached
        if symbol not in self._loaded_data:
            await self._load_csv(symbol)
        
        df = self._loaded_data[symbol].copy()
        
        # Filter by date range
        if start_time:
            df = df[df.index >= start_time]
        if end_time:
            df = df[df.index <= end_time]
        
        # Resample to requested timeframe if needed
        if timeframe != "1d":  # Assuming daily data by default
            freq = self._get_pandas_freq(timeframe)
            df = self._resample_ohlcv(df, freq)
        
        # Apply limit
        if limit and len(df) > limit:
            df = df.iloc[-limit:]
        
        return df
    
    async def _load_csv(self, symbol: str):
        """Load CSV file into memory"""
        file_info = self._available_files[symbol]
        file_path = file_info['path']
        
        try:
            # Read CSV with various date formats
            df = pd.read_csv(
                file_path,
                parse_dates=True,
                index_col=0,  # Assume first column is date
                infer_datetime_format=True
            )
            
            # Standardize column names
            column_mapping = {
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            }
            
            df = df.rename(columns=column_mapping)
            
            # Ensure we have required columns
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in df.columns:
                    if col == 'volume':
                        df[col] = 0  # Default volume to 0 if missing
                    else:
                        raise ValueError(f"Missing required column: {col}")
            
            # Select only OHLCV columns
            df = df[required_columns]
            
            # Ensure numeric types
            for col in required_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Drop rows with NaN values
            df = df.dropna()
            
            # Sort by date
            df = df.sort_index()
            
            # Cache the data
            self._loaded_data[symbol] = df
            
            self.logger.info(f"Loaded {len(df)} rows for {symbol} from CSV")
            
        except Exception as e:
            self.logger.error(f"Error loading CSV file for {symbol}: {e}")
            raise
    
    def _resample_ohlcv(self, df: pd.DataFrame, freq: str) -> pd.DataFrame:
        """Resample OHLCV data to different timeframe"""
        return df.resample(freq).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
    
    def _get_pandas_freq(self, timeframe: str) -> str:
        """Convert timeframe to pandas frequency"""
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
    
    async def fetch_ticker(self, symbol: str) -> Dict:
        """Fetch latest ticker data from CSV"""
        symbol = symbol.upper()
        
        if symbol not in self._loaded_data:
            await self._load_csv(symbol)
        
        df = self._loaded_data[symbol]
        
        if df.empty:
            raise ValueError(f"No data available for {symbol}")
        
        # Get latest row
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        return {
            'bid': float(latest['close']),
            'ask': float(latest['close']),
            'last': float(latest['close']),
            'volume_24h': float(latest['volume']),
            'change_24h': float(latest['close'] - prev['close']),
            'change_24h_pct': float((latest['close'] - prev['close']) / prev['close'] * 100),
            'high_24h': float(latest['high']),
            'low_24h': float(latest['low']),
            'timestamp': int(df.index[-1].timestamp() * 1000)
        }
    
    async def get_symbols(self) -> List[str]:
        """Get list of available symbols from CSV files"""
        await self._scan_files()
        return list(self._available_files.keys())
    
    def is_symbol_valid(self, symbol: str) -> bool:
        """Check if CSV file exists for symbol"""
        return symbol.upper() in self._available_files
    
    async def save_data(self, symbol: str, df: pd.DataFrame) -> bool:
        """Save DataFrame to CSV file"""
        try:
            symbol = symbol.upper()
            file_path = self.data_directory / f"{symbol}.csv"
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save to CSV
            df.to_csv(file_path)
            
            # Update available files
            await self._scan_files()
            
            # Update cache
            self._loaded_data[symbol] = df
            
            self.logger.info(f"Saved {len(df)} rows for {symbol} to CSV")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving CSV file for {symbol}: {e}")
            return False