#!/usr/bin/env python3
import requests
import json
from datetime import datetime

# Test the backtest endpoint
url = "http://localhost:8000/api/v1/backtest/run"
payload = {
    "symbol": "BTC/USD",
    "strategy": "momentum_punch",
    "start_date": "2025-04-01",
    "end_date": "2025-05-01",
    "initial_capital": 10000,
    "position_size": 0.8,
    "stop_loss": 0.02,
    "take_profit": 0.04,
    "timeframe": "4h"
}

try:
    response = requests.post(url, json=payload, timeout=30)
    if response.status_code == 200:
        result = response.json()
        print("Backtest completed successfully!")
        print(f"Backtest ID: {result.get('backtest_id', 'N/A')}")
        print(f"Data points: {result.get('data_points', 0)}")
        print(f"Signals generated: {result.get('signals_generated', 0)}")
        print(f"Trades executed: {len(result.get('trades', []))}")
        print(f"Message: {result.get('message', '')}")
        
        print("\nMetrics:")
        metrics = result.get('metrics', {})
        for key, value in metrics.items():
            print(f"  {key}: {value}")
            
        # Check for NaN values
        nan_metrics = [k for k, v in metrics.items() if v != v]  # NaN != NaN
        if nan_metrics:
            print(f"\nWARNING: Found NaN values in: {nan_metrics}")
            
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"Failed to connect: {e}")