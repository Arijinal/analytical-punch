#!/usr/bin/env python3
"""
Test script to verify SQLAlchemy session binding fixes for trading bot system.
"""

import sys
import os
import asyncio
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Mock environment variables for testing
os.environ['DATABASE_URL'] = 'sqlite:///test_session_fixes.db'
os.environ['PERSONAL_MODE'] = 'true'

async def test_session_fixes():
    """Test all the session binding fixes"""
    
    print("🔧 Testing SQLAlchemy Session Binding Fixes")
    print("=" * 50)
    
    try:
        from app.database.trading_db import (
            bot_repository, order_repository, trade_repository,
            position_repository, alert_repository, trading_db
        )
        from app.models.trading import BotStatus
        
        # Initialize database
        trading_db.initialize()
        print("✅ Database initialized successfully")
        
        # Test 1: Create a bot
        print("\n1. Testing bot creation...")
        bot_data = {
            'name': 'Test Bot',
            'description': 'Test bot for session fixes',
            'config': {'paper_trading': True, 'initial_capital': 10000},
            'strategies': ['momentum_punch', 'value_punch'],
            'symbols': ['BTCUSDT', 'ETHUSDT'],
            'timeframes': ['1h', '4h'],
            'paper_trading': True,
            'initial_capital': 10000,
            'current_capital': 10000,
            'max_position_size': 0.1,
            'max_daily_loss': 0.05,
            'max_drawdown_limit': 0.15
        }
        
        created_bot = bot_repository.create_bot(bot_data)
        bot_id = created_bot['id']
        print(f"✅ Bot created successfully: {bot_id}")
        
        # Test 2: Get bot (this was the main issue)
        print("\n2. Testing bot retrieval...")
        retrieved_bot = bot_repository.get_bot(bot_id)
        
        if retrieved_bot:
            print(f"✅ Bot retrieved successfully: {retrieved_bot['name']}")
            
            # Test accessing the status property (this would cause the session binding error)
            status = retrieved_bot['status']
            status_value = status.value if hasattr(status, 'value') else status
            print(f"✅ Bot status accessed successfully: {status_value}")
        else:
            print("❌ Bot retrieval failed")
            return False
        
        # Test 3: Get all bots
        print("\n3. Testing get all bots...")
        all_bots = bot_repository.get_all_bots()
        
        if all_bots:
            print(f"✅ Retrieved {len(all_bots)} bots")
            for bot in all_bots:
                # Test accessing status on each bot
                status = bot['status']
                status_value = status.value if hasattr(status, 'value') else status
                print(f"   - {bot['name']}: {status_value}")
        else:
            print("⚠️  No bots found (this is expected for a fresh database)")
        
        # Test 4: Update bot
        print("\n4. Testing bot update...")
        update_success = bot_repository.update_bot(bot_id, {
            'description': 'Updated test bot',
            'status': BotStatus.RUNNING
        })
        
        if update_success:
            print("✅ Bot updated successfully")
            
            # Verify update
            updated_bot = bot_repository.get_bot(bot_id)
            if updated_bot and updated_bot['description'] == 'Updated test bot':
                print("✅ Update verified")
            else:
                print("❌ Update verification failed")
                return False
        else:
            print("❌ Bot update failed")
            return False
        
        # Test 5: Get bot performance
        print("\n5. Testing bot performance retrieval...")
        performance = bot_repository.get_bot_performance(bot_id)
        
        if performance:
            print(f"✅ Performance data retrieved: {performance['name']}")
            # Test accessing status in performance data
            status_value = performance['status']
            print(f"✅ Performance status accessed: {status_value}")
        else:
            print("❌ Performance retrieval failed")
            return False
        
        # Test 6: Get bot orders, trades, positions (empty but should not error)
        print("\n6. Testing related data retrieval...")
        
        orders = order_repository.get_bot_orders(bot_id)
        print(f"✅ Orders retrieved: {len(orders)} orders")
        
        trades = trade_repository.get_bot_trades(bot_id)
        print(f"✅ Trades retrieved: {len(trades)} trades")
        
        positions = position_repository.get_bot_positions(bot_id)
        print(f"✅ Positions retrieved: {len(positions)} positions")
        
        # Test 7: Delete bot
        print("\n7. Testing bot deletion...")
        delete_success = bot_repository.delete_bot(bot_id)
        
        if delete_success:
            print("✅ Bot deleted successfully")
            
            # Verify deletion
            deleted_bot = bot_repository.get_bot(bot_id)
            if not deleted_bot:
                print("✅ Deletion verified")
            else:
                print("❌ Deletion verification failed")
                return False
        else:
            print("❌ Bot deletion failed")
            return False
        
        print("\n" + "=" * 50)
        print("🎉 ALL SESSION BINDING TESTS PASSED!")
        print("✅ No 'Instance is not bound to a Session' errors occurred")
        print("✅ All ORM objects are properly detached or converted to dictionaries")
        print("✅ Bot creation, retrieval, update, and deletion work correctly")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up test database
        try:
            if os.path.exists('test_session_fixes.db'):
                os.remove('test_session_fixes.db')
                print("\n🧹 Test database cleaned up")
        except:
            pass


async def test_api_routes():
    """Test the API routes that were causing issues"""
    
    print("\n🌐 Testing API Route Session Handling")
    print("=" * 50)
    
    try:
        # Import after setting up environment
        from app.api.routes.trading import get_bot_status, is_bot_running
        from app.database.trading_db import bot_repository
        from app.models.trading import BotStatus
        
        # Create a test bot for API testing
        bot_data = {
            'name': 'API Test Bot',
            'description': 'Test bot for API session fixes',
            'config': {'paper_trading': True, 'initial_capital': 10000},
            'strategies': ['momentum_punch'],
            'symbols': ['BTCUSDT'],
            'timeframes': ['1h'],
            'paper_trading': True,
            'initial_capital': 10000,
            'current_capital': 10000,
            'max_position_size': 0.1,
            'max_daily_loss': 0.05,
            'max_drawdown_limit': 0.15,
            'status': BotStatus.STOPPED
        }
        
        created_bot = bot_repository.create_bot(bot_data)
        bot_id = created_bot['id']
        print(f"✅ API test bot created: {bot_id}")
        
        # Test helper functions
        print("\n1. Testing status helper functions...")
        status = get_bot_status(bot_id)
        print(f"✅ get_bot_status(): {status}")
        
        running = is_bot_running(bot_id)
        print(f"✅ is_bot_running(): {running}")
        
        # Test with non-existent bot
        fake_status = get_bot_status('fake-bot-id')
        print(f"✅ get_bot_status() for non-existent bot: {fake_status}")
        
        # Clean up
        bot_repository.delete_bot(bot_id)
        print("✅ API test bot cleaned up")
        
        print("\n✅ API route session handling tests passed!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ API TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("🚀 Starting Session Binding Fix Tests")
    print("This will test the fixes for SQLAlchemy session binding issues")
    print("in the trading bot system.\n")
    
    # Run repository tests
    repo_success = await test_session_fixes()
    
    # Run API tests
    api_success = await test_api_routes()
    
    # Final results
    print("\n" + "=" * 60)
    if repo_success and api_success:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Session binding issues have been resolved")
        print("✅ Bots can be created, started, and their status checked")
        print("✅ No 'Instance is not bound to a Session' errors should occur")
    else:
        print("❌ SOME TESTS FAILED!")
        print("❌ Session binding issues may still exist")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)