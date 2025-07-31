import os
from typing import Optional, List, Dict
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.personal')
load_dotenv('.env', override=False)


@lru_cache()
def get_config():
    return Config()


class Config:
    """Configuration for Analytical Punch - dual mode support"""
    
    # Personal mode unlocks everything
    PERSONAL_MODE = os.getenv('PERSONAL_MODE', 'false').lower() == 'true'
    
    # API Configuration
    API_VERSION = 'v1'
    API_PREFIX = f'/api/{API_VERSION}'
    
    # Server Configuration
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 8000))
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
    
    # Database Configuration
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        'postgresql://analytical:punch123@localhost:5432/analytical_punch'
    )
    
    # Redis Configuration
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TTL = int(os.getenv('CACHE_TTL', 300))  # 5 minutes
    
    # CORS Configuration
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',')
    
    # Feature flags based on mode
    if PERSONAL_MODE:
        # Personal mode - unlimited everything
        MAX_INDICATORS = None
        HISTORICAL_DAYS = 3650  # 10 years
        RATE_LIMITS = None
        AVAILABLE_SOURCES = ['binance', 'yahoo', 'csv']
        ENABLE_ML_SIGNALS = True
        ENABLE_USAGE_TRACKING = True
        ENABLE_TRADE_JOURNAL = True
        MAX_CONCURRENT_REQUESTS = None
        CACHE_SIZE_MB = 1000
        ENABLE_BACKTESTING = True
        MAX_BACKTEST_DAYS = 3650
    else:
        # SaaS mode - limited features
        MAX_INDICATORS = 5
        HISTORICAL_DAYS = 90
        RATE_LIMITS = {'requests_per_minute': 60}
        AVAILABLE_SOURCES = ['binance']
        ENABLE_ML_SIGNALS = False
        ENABLE_USAGE_TRACKING = False
        ENABLE_TRADE_JOURNAL = False
        MAX_CONCURRENT_REQUESTS = 10
        CACHE_SIZE_MB = 100
        ENABLE_BACKTESTING = True
        MAX_BACKTEST_DAYS = 180
    
    # Data Source Configuration
    BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
    BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
    
    # Indicator Configuration
    INDICATOR_DEFAULTS = {
        'sma': {'periods': [20, 50, 200]},
        'ema': {'periods': [12, 26, 50]},
        'rsi': {'period': 14, 'overbought': 70, 'oversold': 30},
        'macd': {'fast': 12, 'slow': 26, 'signal': 9},
        'bollinger': {'period': 20, 'std_dev': 2},
        'atr': {'period': 14},
        'stochastic': {'k_period': 14, 'd_period': 3, 'smooth': 3},
        'obv': {},
        'volume_roc': {'period': 14},
        'fibonacci': {'lookback': 100}
    }
    
    # Signal Configuration
    SIGNAL_CONFIDENCE_THRESHOLD = 0.6
    SIGNAL_RISK_REWARD_MIN = 1.5
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # WebSocket Configuration
    WS_HEARTBEAT_INTERVAL = 30
    WS_MESSAGE_QUEUE_SIZE = 1000
    
    @classmethod
    def get_indicator_config(cls, indicator_name: str) -> Dict:
        """Get default configuration for an indicator"""
        return cls.INDICATOR_DEFAULTS.get(indicator_name, {})
    
    @classmethod
    def is_source_available(cls, source: str) -> bool:
        """Check if a data source is available in current mode"""
        return source in cls.AVAILABLE_SOURCES
    
    @classmethod
    def validate_historical_request(cls, days: int) -> int:
        """Validate and limit historical data requests"""
        if cls.PERSONAL_MODE:
            return min(days, cls.HISTORICAL_DAYS)
        return min(days, cls.HISTORICAL_DAYS)