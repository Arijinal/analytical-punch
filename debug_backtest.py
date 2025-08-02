#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import asyncio
from datetime import datetime

# Directly test the components
async def test():
    try:
        # Import components
        from app.data.manager import data_manager
        from app.core.indicators.base import IndicatorManager
        from app.core.signals.generator import SignalGenerator
        from app.core.backtest.metrics import BacktestMetrics
        from app.core.backtest.engine import Portfolio, Trade
        
        print("All imports successful")
        
        # Test basic operations that might cause the error
        # Test 1: Basic arithmetic
        print("\nTest 1: Basic arithmetic")
        a = 1
        b = None
        try:
            c = 1 - b
        except TypeError as e:
            print(f"Error with 1 - None: {e}")
            
        # Test 2: Portfolio operations
        print("\nTest 2: Portfolio operations")
        portfolio = Portfolio(initial_capital=10000, cash=10000)
        print(f"Portfolio created with cash: {portfolio.cash}")
        
        # Test 3: Fetch data
        print("\nTest 3: Fetching data")
        try:
            df = await data_manager.fetch_ohlcv(
                symbol='BTC/USD',
                timeframe='4h',
                start_time=datetime(2025, 5, 2),
                end_time=datetime(2025, 5, 3)
            )
            print(f"Data fetched: {len(df)} rows")
            print(f"Columns: {list(df.columns)}")
            if not df.empty:
                print(f"First close price: {df.iloc[0]['close']}")
        except Exception as e:
            print(f"Error fetching data: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"Import error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())