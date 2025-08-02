"""
API endpoint tests for Analytical Punch
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import json

from app.main import app
from app.config import get_config

config = get_config()
client = TestClient(app)


class TestChartAPI:
    """Test chart-related API endpoints"""
    
    def test_get_chart_data(self):
        """Test fetching chart data"""
        response = client.get("/api/v1/chart/BTC-USD?interval=1h&limit=100")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "candles" in data
        assert "indicators" in data
        assert "signals" in data
        assert "market_info" in data
        
        # Check candle structure
        if data["candles"]:
            candle = data["candles"][0]
            assert all(key in candle for key in ["time", "open", "high", "low", "close", "volume"])
    
    def test_get_chart_with_indicators(self):
        """Test fetching chart data with specific indicators"""
        response = client.get("/api/v1/chart/ETH-USD?indicators=sma,rsi,macd")
        assert response.status_code == 200
        
        data = response.json()
        assert "indicators" in data
        # Check if requested indicators are present
        assert any(ind in data["indicators"] for ind in ["sma", "rsi", "macd"])
    
    def test_invalid_symbol(self):
        """Test handling of invalid symbol"""
        response = client.get("/api/v1/chart/INVALID-SYMBOL")
        assert response.status_code in [404, 500]
    
    def test_get_available_indicators(self):
        """Test fetching available indicators"""
        response = client.get("/api/v1/chart/BTC-USD/indicators")
        assert response.status_code == 200
        
        data = response.json()
        assert "available_indicators" in data
        assert isinstance(data["available_indicators"], list)
    
    def test_get_signals_only(self):
        """Test fetching only trading signals"""
        response = client.get("/api/v1/chart/BTC-USD/signals?timeframe=1h")
        assert response.status_code == 200
        
        data = response.json()
        assert "signals" in data
        assert "total_signals" in data


class TestMarketAPI:
    """Test market-related API endpoints"""
    
    def test_get_symbols(self):
        """Test fetching available symbols"""
        response = client.get("/api/v1/market/symbols")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbols" in data
        assert isinstance(data["symbols"], list)
        assert len(data["symbols"]) > 0
    
    def test_get_ticker(self):
        """Test fetching ticker data"""
        response = client.get("/api/v1/market/ticker/BTC-USD")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "last" in data
        assert "bid" in data
        assert "ask" in data
        assert "volume" in data
    
    def test_validate_symbol(self):
        """Test symbol validation"""
        response = client.get("/api/v1/market/validate/BTC-USD")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "valid" in data
        assert "sources" in data


class TestBacktestAPI:
    """Test backtesting API endpoints"""
    
    def test_run_backtest(self):
        """Test running a backtest"""
        backtest_config = {
            "symbol": "BTC-USD",
            "start_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            "end_date": datetime.now().strftime("%Y-%m-%d"),
            "initial_capital": 10000,
            "strategies": ["momentum_punch"],
            "timeframe": "1h"
        }
        
        response = client.post("/api/v1/backtest/run", json=backtest_config)
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert "metrics" in data
        assert "trades" in data
    
    def test_backtest_invalid_strategy(self):
        """Test backtest with invalid strategy"""
        backtest_config = {
            "symbol": "BTC-USD",
            "strategies": ["invalid_strategy"]
        }
        
        response = client.post("/api/v1/backtest/run", json=backtest_config)
        assert response.status_code in [400, 422]


class TestTradingAPI:
    """Test trading bot API endpoints"""
    
    def test_list_bots(self):
        """Test listing trading bots"""
        response = client.get("/api/v1/trading/bots")
        assert response.status_code == 200
        
        data = response.json()
        assert "bots" in data
        assert isinstance(data["bots"], list)
    
    def test_create_bot(self):
        """Test creating a new trading bot"""
        bot_config = {
            "name": "Test Bot",
            "strategies": ["momentum_punch"],
            "symbols": ["BTC-USD"],
            "initial_capital": 10000,
            "paper_trading": True
        }
        
        response = client.post("/api/v1/trading/bots", json=bot_config)
        assert response.status_code == 200
        
        data = response.json()
        assert "bot_id" in data
        assert "status" in data
    
    def test_bot_operations(self):
        """Test bot start/stop/pause operations"""
        # First create a bot
        bot_config = {
            "name": "Operation Test Bot",
            "strategies": ["trend_punch"],
            "symbols": ["ETH-USD"],
            "initial_capital": 5000,
            "paper_trading": True
        }
        
        create_response = client.post("/api/v1/trading/bots", json=bot_config)
        assert create_response.status_code == 200
        bot_id = create_response.json()["bot_id"]
        
        # Test start
        start_response = client.post(f"/api/v1/trading/bots/{bot_id}/start")
        assert start_response.status_code == 200
        
        # Test pause
        pause_response = client.post(f"/api/v1/trading/bots/{bot_id}/pause")
        assert pause_response.status_code == 200
        
        # Test stop
        stop_response = client.post(f"/api/v1/trading/bots/{bot_id}/stop")
        assert stop_response.status_code == 200
    
    def test_get_bot_status(self):
        """Test getting bot status"""
        # Create a bot first
        bot_config = {
            "name": "Status Test Bot",
            "strategies": ["value_punch"],
            "symbols": ["BTC-USD"],
            "initial_capital": 10000,
            "paper_trading": True
        }
        
        create_response = client.post("/api/v1/trading/bots", json=bot_config)
        bot_id = create_response.json()["bot_id"]
        
        # Get status
        response = client.get(f"/api/v1/trading/bots/{bot_id}/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "bot_id" in data
        assert "status" in data
        assert "portfolio_value" in data
        assert "positions" in data


class TestWebSocket:
    """Test WebSocket connections"""
    
    def test_websocket_connection(self):
        """Test WebSocket connection and subscription"""
        from fastapi.testclient import TestClient
        
        with client.websocket_connect("/ws") as websocket:
            # Test subscription
            websocket.send_json({
                "type": "subscribe",
                "symbol": "BTC-USD",
                "interval": "1m"
            })
            
            # Should receive subscription confirmation
            data = websocket.receive_json()
            assert data["type"] == "subscribed"
            assert data["symbol"] == "BTC-USD"
            
            # Test ping/pong
            websocket.send_json({"type": "ping"})
            data = websocket.receive_json()
            assert data["type"] == "pong"


class TestHealthAndInfo:
    """Test health and info endpoints"""
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "features" in data
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["name"] == "Analytical Punch"


@pytest.mark.parametrize("symbol,expected_status", [
    ("BTC-USD", 200),
    ("ETH-USD", 200),
    ("AAPL", 200),
    ("", 422),
    ("INVALID", 404)
])
def test_chart_data_various_symbols(symbol, expected_status):
    """Test chart endpoint with various symbols"""
    response = client.get(f"/api/v1/chart/{symbol}")
    assert response.status_code == expected_status


@pytest.mark.parametrize("interval", ["1m", "5m", "15m", "30m", "1h", "4h", "1d"])
def test_chart_data_intervals(interval):
    """Test chart endpoint with different intervals"""
    response = client.get(f"/api/v1/chart/BTC-USD?interval={interval}")
    assert response.status_code == 200
    data = response.json()
    assert data["interval"] == interval