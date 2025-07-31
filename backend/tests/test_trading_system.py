"""
Comprehensive testing framework for the trading bot system.
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd
import numpy as np

from app.core.trading.base import (
    Order, OrderType, OrderSide, OrderStatus, Signal, Trade, Position, Portfolio
)
from app.core.trading.exchange import BinanceExchange
from app.core.trading.risk_manager import AdvancedRiskManager, RiskLimits
from app.core.trading.strategies.momentum_punch import MomentumPunchStrategy
from app.core.trading.strategies.value_punch import ValuePunchStrategy
from app.core.trading.strategies.breakout_punch import BreakoutPunchStrategy
from app.core.trading.strategies.trend_punch import TrendPunchStrategy
from app.core.trading.adaptive_bot import AdaptiveMultiStrategyBot
from app.core.trading.order_manager import SmartOrderManager, ExecutionParams, ExecutionStrategy
from app.core.trading.paper_trader import PaperTradingEngine
from app.core.trading.safety import SafetyManager
from app.core.trading.monitoring import RealTimeMonitor
from app.core.trading.analytics import PerformanceAnalyzer


class TestTradingBotBase:
    """Test base trading bot components"""
    
    def test_order_creation(self):
        """Test order creation and properties"""
        order = Order(
            id="test-order-1",
            symbol="BTC/USDT",
            type=OrderType.MARKET,
            side=OrderSide.BUY,
            amount=0.1,
            price=50000.0
        )
        
        assert order.id == "test-order-1"
        assert order.symbol == "BTC/USDT"
        assert order.type == OrderType.MARKET
        assert order.side == OrderSide.BUY
        assert order.amount == 0.1
        assert order.price == 50000.0
        assert order.status == OrderStatus.OPEN
        assert order.remaining_amount == 0.1
        assert not order.is_filled
        assert order.is_active
    
    def test_position_calculation(self):
        """Test position P&L calculations"""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            size=0.1,
            entry_price=50000.0,
            current_price=52000.0,
            entry_time=datetime.utcnow()
        )
        
        assert position.market_value == 5200.0  # 0.1 * 52000
        assert position.pnl_pct == 4.0  # (52000 - 50000) / 50000 * 100
        
        # Test short position
        position.side = "short"
        assert position.pnl_pct == -4.0  # (50000 - 52000) / 50000 * 100
    
    def test_portfolio_updates(self):
        """Test portfolio value updates"""
        portfolio = Portfolio(cash=10000.0)
        
        # Add position
        position = Position(
            symbol="BTC/USDT",
            side="long",
            size=0.1,
            entry_price=50000.0,
            current_price=50000.0,
            entry_time=datetime.utcnow()
        )
        portfolio.positions["BTC/USDT"] = position
        
        # Update with new prices
        current_prices = {"BTC/USDT": 52000.0}
        portfolio.update_portfolio_value(current_prices)
        
        assert position.current_price == 52000.0
        assert position.unrealized_pnl == 200.0  # (52000 - 50000) * 0.1
        assert portfolio.total_value == 15200.0  # 10000 cash + 5200 position value
        assert portfolio.unrealized_pnl == 200.0


class TestExchangeIntegration:
    """Test exchange integration"""
    
    @pytest.fixture
    def mock_exchange(self):
        """Create mock exchange for testing"""
        exchange = BinanceExchange(paper_trading=True)
        return exchange
    
    @pytest.mark.asyncio
    async def test_exchange_connection(self, mock_exchange):
        """Test exchange connection"""
        with patch.object(mock_exchange, 'exchange') as mock_ccxt:
            mock_ccxt.load_markets = AsyncMock()
            
            result = await mock_exchange.connect()
            assert result is True
            assert mock_exchange.connected is True
    
    @pytest.mark.asyncio
    async def test_paper_trading_order(self, mock_exchange):
        """Test paper trading order execution"""
        await mock_exchange.connect()
        
        # Mock ticker data
        with patch.object(mock_exchange, 'get_ticker') as mock_ticker:
            mock_ticker.return_value = {'last': 50000.0}
            
            order = Order(
                id=str(uuid.uuid4()),
                symbol="BTC/USDT",
                type=OrderType.MARKET,
                side=OrderSide.BUY,
                amount=0.1
            )
            
            order_id = await mock_exchange.place_order(order)
            assert order_id is not None
            assert order.status == OrderStatus.FILLED
            assert order.filled_amount == 0.1
    
    @pytest.mark.asyncio
    async def test_balance_retrieval(self, mock_exchange):
        """Test balance retrieval in paper trading"""
        await mock_exchange.connect()
        
        balance = await mock_exchange.get_balance()
        assert isinstance(balance, dict)
        assert 'USDT' in balance
        assert balance['USDT'] == 10000.0  # Default paper trading balance


class TestRiskManagement:
    """Test risk management system"""
    
    @pytest.fixture
    def risk_manager(self):
        """Create risk manager for testing"""
        limits = RiskLimits(
            max_position_size=0.1,
            max_portfolio_risk=0.02,
            max_daily_loss=0.05,
            max_drawdown=0.15
        )
        return AdvancedRiskManager(limits)
    
    def test_position_size_calculation(self, risk_manager):
        """Test position size calculation"""
        signal = Signal(
            id=str(uuid.uuid4()),
            symbol="BTC/USDT",
            direction="buy",
            confidence=0.8,
            price=50000.0,
            timestamp=datetime.utcnow(),
            strategy="test",
            stop_loss=49000.0,
            indicators={}
        )
        
        portfolio = Portfolio(cash=10000.0)
        portfolio.total_value = 10000.0
        
        size = risk_manager.calculate_position_size(signal, portfolio, 0.01)
        
        # With 1% risk and 1000 price risk (50000 - 49000), should be 0.1 BTC
        assert size > 0
        assert size <= 0.1  # Should not exceed max position size
    
    def test_order_validation(self, risk_manager):
        """Test order validation"""
        portfolio = Portfolio(cash=10000.0)
        portfolio.total_value = 10000.0
        
        # Valid order
        valid_order = Order(
            id=str(uuid.uuid4()),
            symbol="BTC/USDT",
            type=OrderType.MARKET,
            side=OrderSide.BUY,
            amount=0.05,  # 5% of portfolio at 50k = $2500 < 10% limit
            price=50000.0
        )
        
        assert risk_manager.validate_order(valid_order, portfolio) is True
        
        # Invalid order (too large)
        invalid_order = Order(
            id=str(uuid.uuid4()),
            symbol="BTC/USDT",
            type=OrderType.MARKET,
            side=OrderSide.BUY,
            amount=0.3,  # 30% of portfolio > 10% limit
            price=50000.0
        )
        
        assert risk_manager.validate_order(invalid_order, portfolio) is False


class TestTradingStrategies:
    """Test trading strategies"""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for testing"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1H')
        
        # Generate realistic price data
        np.random.seed(42)
        returns = np.random.normal(0, 0.02, 100)
        prices = 50000 * np.cumprod(1 + returns)
        
        df = pd.DataFrame({
            'open': prices * (1 + np.random.normal(0, 0.001, 100)),
            'high': prices * (1 + np.abs(np.random.normal(0, 0.005, 100))),
            'low': prices * (1 - np.abs(np.random.normal(0, 0.005, 100))),
            'close': prices,
            'volume': np.random.uniform(100, 1000, 100)
        }, index=dates)
        
        # Ensure OHLC relationships are correct
        df['high'] = np.maximum.reduce([df['open'], df['high'], df['close']])
        df['low'] = np.minimum.reduce([df['open'], df['low'], df['close']])
        
        return df
    
    @pytest.mark.asyncio
    async def test_momentum_strategy(self, sample_data):
        """Test momentum strategy signal generation"""
        strategy = MomentumPunchStrategy()
        
        signals = await strategy.generate_signals("BTC/USDT", sample_data, {})
        
        # Should generate signals (may be empty based on conditions)
        assert isinstance(signals, list)
        
        # If signals generated, they should be valid
        for signal in signals:
            assert isinstance(signal, Signal)
            assert signal.symbol == "BTC/USDT"
            assert signal.direction in ['buy', 'sell']
            assert 0 <= signal.confidence <= 1
            assert signal.strategy == "momentum_punch"
    
    @pytest.mark.asyncio
    async def test_value_strategy(self, sample_data):
        """Test value strategy signal generation"""
        strategy = ValuePunchStrategy()
        
        signals = await strategy.generate_signals("BTC/USDT", sample_data, {})
        
        assert isinstance(signals, list)
        
        for signal in signals:
            assert isinstance(signal, Signal)
            assert signal.strategy == "value_punch"
    
    @pytest.mark.asyncio
    async def test_breakout_strategy(self, sample_data):
        """Test breakout strategy signal generation"""
        strategy = BreakoutPunchStrategy()
        
        signals = await strategy.generate_signals("BTC/USDT", sample_data, {})
        
        assert isinstance(signals, list)
        
        for signal in signals:
            assert isinstance(signal, Signal)
            assert signal.strategy == "breakout_punch"
    
    @pytest.mark.asyncio
    async def test_trend_strategy(self, sample_data):
        """Test trend strategy signal generation"""
        strategy = TrendPunchStrategy()
        
        signals = await strategy.generate_signals("BTC/USDT", sample_data, {})
        
        assert isinstance(signals, list)
        
        for signal in signals:
            assert isinstance(signal, Signal)
            assert signal.strategy == "trend_punch"
    
    def test_strategy_validation(self):
        """Test strategy parameter validation"""
        strategy = MomentumPunchStrategy()
        assert strategy.validate_parameters() is True
        
        # Test with invalid parameters
        invalid_strategy = MomentumPunchStrategy({
            'min_risk_reward': -1.0  # Invalid value
        })
        assert invalid_strategy.validate_parameters() is False


class TestAdaptiveBot:
    """Test adaptive multi-strategy bot"""
    
    @pytest.fixture
    def mock_exchange(self):
        """Create mock exchange"""
        exchange = MagicMock()
        exchange.connect = AsyncMock(return_value=True)
        exchange.disconnect = AsyncMock()
        exchange.get_balance = AsyncMock(return_value={'USDT': 10000.0})
        exchange.get_positions = AsyncMock(return_value={})
        exchange.get_ticker = AsyncMock(return_value={'last': 50000.0})
        return exchange
    
    @pytest.fixture
    def bot_config(self):
        """Create bot configuration"""
        return {
            'paper_trading': True,
            'initial_capital': 10000,
            'max_position_size': 0.1,
            'max_daily_loss': 0.05,
            'update_interval': 60,
            'rebalance_interval': 3600
        }
    
    def test_bot_initialization(self, mock_exchange, bot_config):
        """Test bot initialization"""
        bot = AdaptiveMultiStrategyBot(
            bot_id="test-bot",
            name="Test Bot",
            config=bot_config,
            symbols=["BTC/USDT", "ETH/USDT"],
            timeframes=["1h", "4h"]
        )
        
        assert bot.bot_id == "test-bot"
        assert bot.name == "Test Bot"
        assert len(bot.strategies) == 4  # 4 punch strategies
        assert len(bot.symbols) == 2
        assert bot.paper_trading is True
    
    def test_strategy_allocation(self, mock_exchange, bot_config):
        """Test strategy allocation system"""
        bot = AdaptiveMultiStrategyBot(
            bot_id="test-bot",
            name="Test Bot",
            config=bot_config,
            symbols=["BTC/USDT"],
            timeframes=["1h"]
        )
        
        # Initial allocations should sum to 1.0
        total_allocation = sum(bot.strategy_allocations.values())
        assert abs(total_allocation - 1.0) < 0.01
        
        # All strategies should have some allocation
        for allocation in bot.strategy_allocations.values():
            assert allocation > 0


class TestOrderExecution:
    """Test smart order execution system"""
    
    @pytest.fixture
    def mock_exchange(self):
        """Create mock exchange for order execution"""
        exchange = MagicMock()
        exchange.get_ticker = AsyncMock(return_value={
            'bid': 49950.0,
            'ask': 50050.0,
            'last': 50000.0
        })
        exchange.get_order_book = AsyncMock(return_value={
            'bids': [[49950, 1.0], [49940, 2.0]],
            'asks': [[50050, 1.0], [50060, 2.0]]
        })
        exchange.place_order = AsyncMock(return_value="order-123")
        exchange.get_order_status = AsyncMock()
        return exchange
    
    @pytest.mark.asyncio
    async def test_immediate_execution(self, mock_exchange):
        """Test immediate order execution"""
        order_manager = SmartOrderManager(mock_exchange)
        
        signal = Signal(
            id=str(uuid.uuid4()),
            symbol="BTC/USDT",
            direction="buy",
            confidence=0.8,
            price=50000.0,
            timestamp=datetime.utcnow(),
            strategy="test",
            indicators={}
        )
        
        # Mock filled order
        filled_order = Order(
            id="order-123",
            symbol="BTC/USDT",
            type=OrderType.MARKET,
            side=OrderSide.BUY,
            amount=0.1,
            filled_amount=0.1,
            filled_price=50025.0,
            status=OrderStatus.FILLED,
            commission=0.5
        )
        mock_exchange.get_order_status.return_value = filled_order
        
        execution_params = ExecutionParams(strategy=ExecutionStrategy.IMMEDIATE)
        report = await order_manager.execute_order(signal, 0.1, execution_params)
        
        assert report.success is True
        assert report.executed_amount == 0.1
        assert report.strategy_used == ExecutionStrategy.IMMEDIATE
    
    @pytest.mark.asyncio
    async def test_twap_execution(self, mock_exchange):
        """Test TWAP execution strategy"""
        order_manager = SmartOrderManager(mock_exchange)
        
        signal = Signal(
            id=str(uuid.uuid4()),
            symbol="BTC/USDT",
            direction="buy",
            confidence=0.8,
            price=50000.0,
            timestamp=datetime.utcnow(),
            strategy="test",
            indicators={}
        )
        
        # Mock multiple filled orders for chunks
        filled_order = Order(
            id="order-123",
            symbol="BTC/USDT",
            type=OrderType.MARKET,
            side=OrderSide.BUY,
            amount=0.02,  # Chunk size
            filled_amount=0.02,
            filled_price=50000.0,
            status=OrderStatus.FILLED,
            commission=0.1
        )
        mock_exchange.get_order_status.return_value = filled_order
        
        execution_params = ExecutionParams(
            strategy=ExecutionStrategy.TWAP,
            chunk_size=0.02,
            time_limit=60
        )
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            report = await order_manager.execute_order(signal, 0.1, execution_params)
        
        assert report.strategy_used == ExecutionStrategy.TWAP
        assert report.chunks_executed > 1


class TestPaperTrading:
    """Test paper trading engine"""
    
    @pytest.fixture
    def paper_engine(self):
        """Create paper trading engine"""
        mock_exchange = MagicMock()
        mock_exchange.get_ticker = AsyncMock(return_value={'last': 50000.0})
        return PaperTradingEngine(mock_exchange)
    
    @pytest.mark.asyncio
    async def test_account_creation(self, paper_engine):
        """Test paper trading account creation"""
        account_id = await paper_engine.create_account(initial_balance=50000.0)
        
        assert account_id is not None
        assert account_id in paper_engine.accounts
        
        account = paper_engine.accounts[account_id]
        assert account.initial_balance == 50000.0
        assert account.current_balance == 50000.0
    
    @pytest.mark.asyncio
    async def test_paper_order_execution(self, paper_engine):
        """Test paper order execution"""
        account_id = await paper_engine.create_account()
        
        order = Order(
            id=str(uuid.uuid4()),
            symbol="BTC/USDT",
            type=OrderType.MARKET,
            side=OrderSide.BUY,
            amount=0.1,
            price=50000.0
        )
        
        result = await paper_engine.place_order(account_id, order)
        
        assert result == order.id
        assert order.status == OrderStatus.FILLED
        assert order.filled_amount == 0.1
        
        # Check account balance updated
        account = paper_engine.accounts[account_id]
        assert account.current_balance < 10000.0  # Should be reduced by purchase


class TestSafetySystem:
    """Test safety and monitoring systems"""
    
    @pytest.fixture
    def safety_manager(self):
        """Create safety manager"""
        return SafetyManager()
    
    def test_safety_rule_initialization(self, safety_manager):
        """Test safety rule initialization"""
        assert len(safety_manager.safety_rules) > 0
        assert len(safety_manager.kill_switches) > 0
        
        # Check default rules exist
        assert 'max_drawdown' in safety_manager.safety_rules
        assert 'daily_loss_limit' in safety_manager.safety_rules
        assert 'emergency_stop' in safety_manager.kill_switches
    
    @pytest.mark.asyncio
    async def test_kill_switch_activation(self, safety_manager):
        """Test manual kill switch activation"""
        result = await safety_manager.manual_kill_switch('emergency_stop', 'test_user')
        
        assert result is True
        kill_switch = safety_manager.kill_switches['emergency_stop']
        assert kill_switch.activated_at is not None
        assert kill_switch.activated_by == 'test_user'


class TestPerformanceAnalytics:
    """Test performance analytics system"""
    
    @pytest.fixture
    def analyzer(self):
        """Create performance analyzer"""
        return PerformanceAnalyzer()
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trades for analysis"""
        trades = []
        base_time = datetime.utcnow() - timedelta(days=30)
        
        for i in range(20):
            trade = Trade(
                id=str(uuid.uuid4()),
                symbol="BTC/USDT",
                side="long",
                entry_price=50000 + np.random.normal(0, 1000),
                exit_price=50000 + np.random.normal(200, 1500),  # Slight positive bias
                size=0.1,
                entry_time=base_time + timedelta(days=i),
                exit_time=base_time + timedelta(days=i, hours=6),
                pnl=np.random.normal(100, 500),
                pnl_pct=np.random.normal(0.5, 2.0),
                commission=10.0,
                exit_reason="take_profit",
                strategy="momentum_punch"
            )
            trades.append(trade)
        
        return trades
    
    def test_sharpe_ratio_calculation(self, analyzer):
        """Test Sharpe ratio calculation"""
        daily_returns = [0.01, -0.005, 0.02, -0.01, 0.015, 0.008, -0.003]
        
        sharpe = analyzer._calculate_sharpe_ratio(daily_returns)
        
        assert isinstance(sharpe, float)
        assert not np.isnan(sharpe)
    
    def test_drawdown_analysis(self, analyzer):
        """Test drawdown analysis"""
        equity_curve = [
            (datetime.utcnow() - timedelta(days=i), 10000 + i * 100 - (i**2 if i > 5 else 0))
            for i in range(20)
        ]
        
        max_dd, max_dd_duration, dd_periods = analyzer._analyze_drawdowns(equity_curve)
        
        assert isinstance(max_dd, float)
        assert max_dd >= 0
        assert isinstance(max_dd_duration, int)
        assert isinstance(dd_periods, list)
    
    def test_strategy_performance_analysis(self, analyzer, sample_trades):
        """Test strategy performance breakdown"""
        strategy_perf = analyzer._analyze_strategy_performance(sample_trades)
        
        assert 'momentum_punch' in strategy_perf
        assert 'total_trades' in strategy_perf['momentum_punch']
        assert 'win_rate' in strategy_perf['momentum_punch']
        assert 'profit_factor' in strategy_perf['momentum_punch']


class TestIntegration:
    """Integration tests for the complete system"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test complete trading workflow"""
        # Create mock exchange
        mock_exchange = MagicMock()
        mock_exchange.connect = AsyncMock(return_value=True)
        mock_exchange.disconnect = AsyncMock()
        mock_exchange.get_balance = AsyncMock(return_value={'USDT': 10000.0})
        mock_exchange.get_positions = AsyncMock(return_value={})
        mock_exchange.get_ticker = AsyncMock(return_value={'last': 50000.0})
        mock_exchange.place_order = AsyncMock(return_value="order-123")
        
        # Create bot configuration
        config = {
            'paper_trading': True,
            'initial_capital': 10000,
            'max_position_size': 0.1,
            'max_daily_loss': 0.05
        }
        
        # Create adaptive bot
        bot = AdaptiveMultiStrategyBot(
            bot_id="integration-test-bot",
            name="Integration Test Bot",
            config=config,
            symbols=["BTC/USDT"],
            timeframes=["1h"]
        )
        
        # Mock data manager
        with patch('app.data.manager.data_manager') as mock_data_manager:
            # Create sample OHLCV data
            dates = pd.date_range(start='2023-01-01', periods=100, freq='1H')
            df = pd.DataFrame({
                'open': [50000] * 100,
                'high': [51000] * 100,
                'low': [49000] * 100,
                'close': [50000 + i * 10 for i in range(100)],  # Trending up
                'volume': [1000] * 100
            }, index=dates)
            
            mock_data_manager.fetch_ohlcv = AsyncMock(return_value=df)
            
            # Test bot status
            status = bot.get_status()
            assert status['bot_id'] == "integration-test-bot"
            assert status['status'] == 'stopped'
    
    @pytest.mark.asyncio
    async def test_system_monitoring(self):
        """Test system monitoring integration"""
        safety_manager = SafetyManager()
        monitor = RealTimeMonitor(safety_manager)
        
        # Test monitoring initialization
        assert monitor.monitoring_active is False
        assert len(monitor.monitored_bots) == 0
        
        # Mock bot for monitoring
        mock_bot = MagicMock()
        mock_bot.bot_id = "test-bot"
        mock_bot.name = "Test Bot"
        mock_bot.status.value = "running"
        mock_bot.portfolio = Portfolio(cash=10000.0)
        mock_bot.add_signal_handler = MagicMock()
        mock_bot.add_trade_handler = MagicMock()
        mock_bot.add_error_handler = MagicMock()
        
        # Register bot
        monitor.register_bot(mock_bot)
        
        assert len(monitor.monitored_bots) == 1
        assert "test-bot" in monitor.monitored_bots


# Performance benchmarks
class TestPerformance:
    """Performance and benchmark tests"""
    
    @pytest.mark.asyncio
    async def test_strategy_performance(self):
        """Benchmark strategy signal generation speed"""
        import time
        
        # Create large dataset
        dates = pd.date_range(start='2023-01-01', periods=1000, freq='1H')
        df = pd.DataFrame({
            'open': np.random.uniform(49000, 51000, 1000),
            'high': np.random.uniform(50000, 52000, 1000),
            'low': np.random.uniform(48000, 50000, 1000),
            'close': np.random.uniform(49000, 51000, 1000),
            'volume': np.random.uniform(100, 1000, 1000)
        }, index=dates)
        
        strategy = MomentumPunchStrategy()
        
        start_time = time.time()
        signals = await strategy.generate_signals("BTC/USDT", df, {})
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Should process 1000 candles in reasonable time (< 1 second)
        assert execution_time < 1.0
        assert isinstance(signals, list)
    
    def test_risk_calculation_performance(self):
        """Benchmark risk calculation performance"""
        import time
        
        risk_manager = AdvancedRiskManager()
        
        # Create large portfolio
        portfolio = Portfolio(cash=100000.0)
        for i in range(100):
            position = Position(
                symbol=f"SYMBOL{i}/USDT",
                side="long",
                size=0.1,
                entry_price=1000.0,
                current_price=1010.0,
                entry_time=datetime.utcnow()
            )
            portfolio.positions[f"SYMBOL{i}/USDT"] = position
        
        start_time = time.time()
        risk_check = risk_manager.check_portfolio_risk(portfolio)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Should calculate risk for 100 positions quickly
        assert execution_time < 0.1
        assert isinstance(risk_check, dict)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])