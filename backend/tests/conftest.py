"""
Test configuration and fixtures for the trading bot system.
"""

import pytest
import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import pandas as pd
import numpy as np

from app.database.trading_db import TradingDatabase
from app.core.trading.base import Portfolio, Position, Trade, Signal
from app.core.trading.exchange import BinanceExchange


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_database():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        db_path = tmp.name
    
    database_url = f"sqlite:///{db_path}"
    db = TradingDatabase(database_url)
    db.initialize()
    
    yield db
    
    # Cleanup
    db.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)  # For reproducible tests
    
    dates = pd.date_range(start='2023-01-01', periods=200, freq='1H')
    
    # Generate realistic price movements
    returns = np.random.normal(0, 0.01, 200)  # 1% hourly volatility
    prices = 50000 * np.cumprod(1 + returns)
    
    # Add some trend and patterns
    trend = np.linspace(0, 0.1, 200)  # 10% upward trend over period
    prices = prices * (1 + trend)
    
    df = pd.DataFrame({
        'open': prices * (1 + np.random.normal(0, 0.001, 200)),
        'high': prices * (1 + np.abs(np.random.normal(0, 0.005, 200))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.005, 200))),
        'close': prices,
        'volume': np.random.uniform(100, 2000, 200)
    }, index=dates)
    
    # Ensure OHLC relationships are correct
    df['high'] = np.maximum.reduce([df['open'], df['high'], df['close']])
    df['low'] = np.minimum.reduce([df['open'], df['low'], df['close']])
    
    return df


@pytest.fixture
def sample_trades():
    """Generate sample trades for testing."""
    trades = []
    base_time = datetime.utcnow() - timedelta(days=30)
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'ADA/USDT']
    strategies = ['momentum_punch', 'value_punch', 'breakout_punch', 'trend_punch']
    
    np.random.seed(42)
    
    for i in range(50):
        entry_price = np.random.uniform(30000, 70000)
        
        # Create bias toward profitable trades (60% win rate)
        if np.random.random() < 0.6:
            # Winning trade
            exit_price = entry_price * np.random.uniform(1.01, 1.05)
            exit_reason = np.random.choice(['take_profit', 'manual'])
        else:
            # Losing trade
            exit_price = entry_price * np.random.uniform(0.95, 0.99)
            exit_reason = np.random.choice(['stop_loss', 'manual'])
        
        size = np.random.uniform(0.01, 0.1)
        pnl = (exit_price - entry_price) * size
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        
        trade = Trade(
            id=f"trade-{i}",
            symbol=np.random.choice(symbols),
            side="long",
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
            entry_time=base_time + timedelta(hours=i*2),
            exit_time=base_time + timedelta(hours=i*2+1),
            pnl=pnl,
            pnl_pct=pnl_pct,
            commission=abs(pnl) * 0.001,  # 0.1% commission
            exit_reason=exit_reason,
            strategy=np.random.choice(strategies)
        )
        
        trades.append(trade)
    
    return trades


@pytest.fixture
def sample_portfolio():
    """Create a sample portfolio for testing."""
    portfolio = Portfolio(cash=50000.0)
    
    # Add some positions
    positions = [
        Position(
            symbol="BTC/USDT",
            side="long",
            size=0.5,
            entry_price=45000.0,
            current_price=47000.0,
            entry_time=datetime.utcnow() - timedelta(hours=2)
        ),
        Position(
            symbol="ETH/USDT",
            side="long",
            size=5.0,
            entry_price=3000.0,
            current_price=3100.0,
            entry_time=datetime.utcnow() - timedelta(hours=1)
        )
    ]
    
    for pos in positions:
        portfolio.positions[pos.symbol] = pos
    
    # Update portfolio value
    current_prices = {
        "BTC/USDT": 47000.0,
        "ETH/USDT": 3100.0
    }
    portfolio.update_portfolio_value(current_prices)
    
    return portfolio


@pytest.fixture
def sample_signals():
    """Generate sample signals for testing."""
    signals = []
    base_time = datetime.utcnow()
    
    symbols = ['BTC/USDT', 'ETH/USDT']
    strategies = ['momentum_punch', 'value_punch']
    directions = ['buy', 'sell']
    
    for i in range(10):
        signal = Signal(
            id=f"signal-{i}",
            symbol=np.random.choice(symbols),
            direction=np.random.choice(directions),
            confidence=np.random.uniform(0.6, 0.95),
            price=np.random.uniform(40000, 60000),
            timestamp=base_time + timedelta(minutes=i*10),
            strategy=np.random.choice(strategies),
            indicators={
                'rsi': np.random.uniform(30, 70),
                'macd': np.random.uniform(-100, 100),
                'volume_ratio': np.random.uniform(0.8, 2.0)
            },
            stop_loss=np.random.uniform(35000, 45000),
            take_profit=np.random.uniform(55000, 65000),
            risk_reward_ratio=np.random.uniform(1.5, 3.0)
        )
        signals.append(signal)
    
    return signals


@pytest.fixture
def mock_binance_exchange():
    """Create a mock Binance exchange for testing."""
    exchange = MagicMock(spec=BinanceExchange)
    
    # Mock connection methods
    exchange.connect = AsyncMock(return_value=True)
    exchange.disconnect = AsyncMock()
    
    # Mock market data methods
    exchange.get_ticker = AsyncMock(return_value={
        'bid': 49950.0,
        'ask': 50050.0,
        'last': 50000.0,
        'volume': 1000.0,
        'change': 500.0,
        'percentage': 1.0,
        'high': 51000.0,
        'low': 49000.0,
        'timestamp': datetime.utcnow().timestamp() * 1000
    })
    
    exchange.get_order_book = AsyncMock(return_value={
        'bids': [[49950, 1.0], [49940, 2.0], [49930, 3.0]],
        'asks': [[50050, 1.0], [50060, 2.0], [50070, 3.0]],
        'timestamp': datetime.utcnow().timestamp() * 1000,
        'symbol': 'BTC/USDT'
    })
    
    exchange.get_balance = AsyncMock(return_value={
        'USDT': 10000.0,
        'BTC': 0.2,
        'ETH': 3.0
    })
    
    exchange.get_positions = AsyncMock(return_value={})
    
    # Mock trading methods
    exchange.place_order = AsyncMock(return_value='order-123')
    exchange.cancel_order = AsyncMock(return_value=True)
    
    # Mock order status
    from app.core.trading.base import Order, OrderType, OrderSide, OrderStatus
    mock_order = Order(
        id='order-123',
        symbol='BTC/USDT',
        type=OrderType.MARKET,
        side=OrderSide.BUY,
        amount=0.1,
        status=OrderStatus.FILLED,
        filled_amount=0.1,
        filled_price=50000.0,
        commission=5.0
    )
    exchange.get_order_status = AsyncMock(return_value=mock_order)
    
    # Mock validation methods
    exchange.validate_symbol = AsyncMock(return_value=True)
    exchange.get_minimum_order_size = AsyncMock(return_value=0.001)
    exchange.get_price_precision = AsyncMock(return_value=2)
    exchange.get_amount_precision = AsyncMock(return_value=6)
    
    return exchange


@pytest.fixture
def bot_config():
    """Standard bot configuration for testing."""
    return {
        'name': 'Test Bot',
        'description': 'A test trading bot',
        'symbols': ['BTC/USDT', 'ETH/USDT'],
        'timeframes': ['1h', '4h'],
        'paper_trading': True,
        'initial_capital': 10000.0,
        'max_position_size': 0.1,
        'max_daily_loss': 0.05,
        'max_drawdown': 0.15,
        'max_open_positions': 5,
        'update_interval': 60,
        'rebalance_interval': 3600,
        'momentum_params': {
            'rsi_period': 14,
            'min_confidence': 0.7
        },
        'value_params': {
            'rsi_extreme_high': 75,
            'rsi_extreme_low': 25
        },
        'breakout_params': {
            'range_periods': 20,
            'min_confidence': 0.65
        },
        'trend_params': {
            'sma_fast': 20,
            'sma_slow': 50,
            'min_confidence': 0.7
        }
    }


@pytest.fixture
def market_data_cache():
    """Create cached market data for testing."""
    cache = {}
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'ADA/USDT']
    
    for symbol in symbols:
        base_price = np.random.uniform(30000, 60000) if 'BTC' in symbol else np.random.uniform(2000, 4000)
        
        cache[symbol] = {
            'bid': base_price * 0.999,
            'ask': base_price * 1.001,
            'last': base_price,
            'volume': np.random.uniform(1000, 10000),
            'change': np.random.uniform(-1000, 1000),
            'percentage': np.random.uniform(-5, 5),
            'high': base_price * 1.02,
            'low': base_price * 0.98,
            'timestamp': datetime.utcnow()
        }
    
    return cache


@pytest.fixture(autouse=True)
def setup_logging():
    """Setup logging for tests."""
    import logging
    
    # Reduce log level during tests to avoid spam
    logging.getLogger('app').setLevel(logging.WARNING)
    
    yield
    
    # Reset logging after tests
    logging.getLogger('app').setLevel(logging.INFO)


@pytest.fixture
def mock_data_manager():
    """Mock data manager for testing."""
    from unittest.mock import patch
    
    with patch('app.data.manager.data_manager') as mock_dm:
        # Mock OHLCV data fetch
        mock_dm.fetch_ohlcv = AsyncMock()
        
        yield mock_dm


# Performance testing fixtures
@pytest.fixture
def large_dataset():
    """Create large dataset for performance testing."""
    np.random.seed(42)
    
    dates = pd.date_range(start='2020-01-01', periods=10000, freq='1H')
    
    # Generate price data with trends and volatility
    returns = np.random.normal(0, 0.005, 10000)
    prices = 50000 * np.cumprod(1 + returns)
    
    df = pd.DataFrame({
        'open': prices * (1 + np.random.normal(0, 0.001, 10000)),
        'high': prices * (1 + np.abs(np.random.normal(0, 0.003, 10000))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.003, 10000))),
        'close': prices,
        'volume': np.random.uniform(100, 5000, 10000)
    }, index=dates)
    
    # Ensure OHLC relationships
    df['high'] = np.maximum.reduce([df['open'], df['high'], df['close']])
    df['low'] = np.minimum.reduce([df['open'], df['low'], df['close']])
    
    return df


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance benchmarks"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add slow marker to tests that might be slow
        if "performance" in item.name or "benchmark" in item.name:
            item.add_marker(pytest.mark.slow)
        
        # Add integration marker to integration tests
        if "integration" in item.name or "end_to_end" in item.name:
            item.add_marker(pytest.mark.integration)