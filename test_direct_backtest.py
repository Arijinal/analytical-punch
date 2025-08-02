#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import asyncio
from datetime import datetime
from app.core.backtest.engine import BacktestEngine

async def test():
    engine = BacktestEngine()
    
    # Test with minimal parameters
    try:
        result = await engine.run(
            symbol='BTC/USD',
            strategy='momentum_punch',
            start_date=datetime(2025, 5, 2),
            end_date=datetime(2025, 5, 3),
            initial_capital=10000,
            position_size=0.8,
            stop_loss=0.02,
            take_profit=0.04,
            timeframe='4h',
            commission=0.001,
            slippage=0.0005
        )
        print("Success!")
        print(f"Trades: {len(result.get('trades', []))}")
        print(f"Metrics: {result.get('metrics', {}).get('total_trades', 'N/A')}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())