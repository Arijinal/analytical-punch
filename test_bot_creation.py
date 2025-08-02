#!/usr/bin/env python3
"""Test bot creation to verify fixes work"""

import requests
import json

# API endpoint
url = "http://localhost:8000/api/v1/trading/bots"

# Bot configuration
bot_data = {
    "name": "Test Bot Fix",
    "symbols": ["BTC-USD"],
    "capital": 10000,
    "paper_trading": True,
    "strategies": ["momentum_punch"],
    "config": {
        "max_position_size": 0.1,
        "max_portfolio_risk": 0.02,
        "momentum_params": {
            "rsi_period": 14
        }
    }
}

print("Creating bot with configuration:")
print(json.dumps(bot_data, indent=2))
print("\nSending request...")

try:
    response = requests.post(url, json=bot_data)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        bot_id = response.json().get('bot_id')  # Fixed: use 'bot_id' not 'id'
        print(f"\n✅ Bot created successfully with ID: {bot_id}")
        
        # Now test starting the bot
        if bot_id:
            print("\nTesting bot start...")
            start_url = f"http://localhost:8000/api/v1/trading/bots/{bot_id}/start"
            start_response = requests.post(start_url)
            print(f"Start Status Code: {start_response.status_code}")
            print(f"Start Response: {json.dumps(start_response.json(), indent=2)}")
            
            # Check bot status
            print("\nChecking bot status...")
            status_url = f"http://localhost:8000/api/v1/trading/bots/{bot_id}"
            status_response = requests.get(status_url)
            print(f"Status Response: {json.dumps(status_response.json(), indent=2)}")
    else:
        print("\n❌ Bot creation failed")
        
except Exception as e:
    print(f"\n❌ Error: {e}")