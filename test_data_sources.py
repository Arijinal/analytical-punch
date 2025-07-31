#!/usr/bin/env python3
"""
Test script to verify data source connections are working
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.data.sources.coingecko import CoinGeckoDataSource
from backend.app.data.sources.kraken import KrakenDataSource
from backend.app.data.sources.coinbase import CoinbaseDataSource
from backend.app.utils.symbol_normalizer import symbol_normalizer


async def test_data_source(source_class, source_name, symbol):
    """Test a single data source"""
    print(f"\n🔍 Testing {source_name}...")
    
    try:
        # Initialize source
        source = source_class()
        
        # Test connection
        connected = await source.connect()
        if not connected:
            print(f"❌ {source_name}: Connection failed")
            return False
        
        print(f"✅ {source_name}: Connected successfully")
        
        # Convert symbol for this source
        source_symbol = symbol_normalizer.convert_for_source(symbol, source_name.lower())
        print(f"   Symbol: {symbol} -> {source_symbol}")
        
        # Test OHLCV data
        try:
            df = await source.fetch_ohlcv(source_symbol, '1h', limit=5)
            if df.empty:
                print(f"❌ {source_name}: No OHLCV data returned")
                return False
            
            print(f"✅ {source_name}: OHLCV data retrieved ({len(df)} candles)")
            print(f"   Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
            
        except Exception as e:
            print(f"❌ {source_name}: OHLCV error - {e}")
            return False
        
        # Test ticker data
        try:
            ticker = await source.fetch_ticker(source_symbol)
            print(f"✅ {source_name}: Ticker data retrieved")
            print(f"   Last price: ${ticker.get('last', 0):.2f}")
            
        except Exception as e:
            print(f"⚠️ {source_name}: Ticker error - {e}")
        
        # Disconnect
        await source.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ {source_name}: General error - {e}")
        return False


async def test_symbol_normalizer():
    """Test symbol normalization"""
    print("\n🔧 Testing Symbol Normalizer...")
    
    test_symbols = [
        'BTC/USDT',
        'BTC-USD', 
        'BTCUSDT',
        'ETH/USD',
        'AAPL'
    ]
    
    for symbol in test_symbols:
        normalized = symbol_normalizer.normalize_symbol(symbol)
        info = symbol_normalizer.get_symbol_info(symbol)
        print(f"   {symbol} -> {normalized} ({info['type']})")
    
    print("✅ Symbol normalizer working")


async def main():
    """Main test function"""
    print("🚀 Starting Data Source Connection Tests...")
    
    # Test symbol normalizer first
    await test_symbol_normalizer()
    
    # Test symbol
    test_symbol = 'BTC-USD'
    print(f"\n📊 Testing with symbol: {test_symbol}")
    
    # Test each data source
    sources_to_test = [
        (CoinGeckoDataSource, 'CoinGecko'),
        (KrakenDataSource, 'Kraken'),
        (CoinbaseDataSource, 'Coinbase')
    ]
    
    results = []
    for source_class, source_name in sources_to_test:
        success = await test_data_source(source_class, source_name, test_symbol)
        results.append((source_name, success))
    
    # Summary
    print("\n📋 Test Results Summary:")
    working_sources = []
    for source_name, success in results:
        status = "✅ Working" if success else "❌ Failed"
        print(f"   {source_name}: {status}")
        if success:
            working_sources.append(source_name)
    
    if working_sources:
        print(f"\n🎉 {len(working_sources)} out of {len(results)} sources are working!")
        print(f"Working sources: {', '.join(working_sources)}")
        return True
    else:
        print(f"\n💥 No data sources are working!")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)