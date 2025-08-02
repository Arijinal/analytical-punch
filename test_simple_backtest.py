#!/usr/bin/env python3
import requests
import json

# Test with minimal date range
url = "http://localhost:8000/api/v1/backtest/run"
payload = {
    "symbol": "BTC/USD",
    "strategy": "momentum_punch",
    "start_date": "2025-01-01",
    "end_date": "2025-01-02",  # Just 1 day
    "initial_capital": 10000,
    "position_size": 0.1,  # 10%
    "timeframe": "1d"  # Daily timeframe
}

print("Testing minimal backtest...")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(url, json=payload, timeout=60)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("\nBacktest completed!")
        print(f"Data points: {result.get('data_points', 0)}")
        print(f"Signals: {result.get('signals_generated', 0)}")
        print(f"Trades: {len(result.get('trades', []))}")
        print(f"Message: {result.get('message', '')}")
        
        metrics = result.get('metrics', {})
        print("\nKey metrics:")
        print(f"  Total return: {metrics.get('total_return_pct', 'N/A')}%")
        print(f"  Total trades: {metrics.get('total_trades', 'N/A')}")
        print(f"  Win rate: {metrics.get('win_rate', 'N/A')}")
    else:
        print(f"Error: {response.text}")
        
except requests.exceptions.Timeout:
    print("Request timed out after 60 seconds")
except Exception as e:
    print(f"Error: {e}")