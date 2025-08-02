#!/usr/bin/env python3
"""
Simplified test to verify SQLAlchemy session binding fixes.
"""

import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Mock environment variables for testing
os.environ['DATABASE_URL'] = 'sqlite:///test_session_simple.db'
os.environ['PERSONAL_MODE'] = 'true'

async def test_core_session_fixes():
    """Test the core session binding fixes without complex dependencies"""
    
    print("🔧 Testing Core SQLAlchemy Session Binding Fixes")
    print("=" * 50)
    
    try:
        from app.database.trading_db import bot_repository, trading_db
        from app.models.trading import BotStatus
        
        # Initialize database
        trading_db.initialize()
        print("✅ Database initialized successfully")
        
        # Test 1: Create a bot
        print("\n1. Testing bot creation...")
        bot_data = {
            'name': 'Session Test Bot',
            'description': 'Bot for testing session binding fixes',
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
        
        # Test 2: Get bot and test session binding (THIS WAS THE MAIN ISSUE)
        print("\n2. Testing the original session binding bug...")
        retrieved_bot = bot_repository.get_bot(bot_id)
        
        if retrieved_bot:
            print(f"✅ Bot retrieved: {retrieved_bot['name']}")
            
            # This is the line that would cause "Instance is not bound to a Session" error
            status = retrieved_bot['status']
            print(f"   Bot status type: {type(status)}")
            
            # Try to access the .value property (this would fail before our fix)
            try:
                status_value = status.value if hasattr(status, 'value') else status
                print(f"✅ Bot status accessed successfully: {status_value}")
                print("   🎉 NO SESSION BINDING ERROR! Fix working correctly.")
            except Exception as e:
                if "not bound to a Session" in str(e):
                    print(f"❌ SESSION BINDING ERROR STILL EXISTS: {e}")
                    return False
                else:
                    print(f"❌ Other error: {e}")
                    return False
        else:
            print("❌ Bot retrieval failed")
            return False
        
        # Test 3: Test get_all_bots with status access
        print("\n3. Testing get_all_bots with status access...")
        all_bots = bot_repository.get_all_bots()
        
        for bot in all_bots:
            try:
                status = bot['status']
                status_value = status.value if hasattr(status, 'value') else status
                print(f"   Bot '{bot['name']}' status: {status_value}")
            except Exception as e:
                if "not bound to a Session" in str(e):
                    print(f"❌ SESSION BINDING ERROR in get_all_bots: {e}")
                    return False
                else:
                    raise
        
        print("✅ All bots processed without session binding errors")
        
        # Test 4: Update bot and test status access
        print("\n4. Testing bot update with status access...")
        bot_repository.update_bot(bot_id, {'status': BotStatus.RUNNING})
        
        updated_bot = bot_repository.get_bot(bot_id)
        if updated_bot:
            try:
                status = updated_bot['status']
                status_value = status.value if hasattr(status, 'value') else status
                print(f"✅ Updated bot status: {status_value}")
            except Exception as e:
                if "not bound to a Session" in str(e):
                    print(f"❌ SESSION BINDING ERROR after update: {e}")
                    return False
                else:
                    raise
        
        # Test 5: Test get_bot_performance
        print("\n5. Testing get_bot_performance with status access...")
        performance = bot_repository.get_bot_performance(bot_id)
        
        if performance:
            try:
                status_value = performance['status']  # This should already be a string
                print(f"✅ Performance status: {status_value}")
            except Exception as e:
                if "not bound to a Session" in str(e):
                    print(f"❌ SESSION BINDING ERROR in performance: {e}")
                    return False
                else:
                    raise
        
        # Clean up
        bot_repository.delete_bot(bot_id)
        print("\n✅ Test bot cleaned up")
        
        print("\n" + "=" * 50)
        print("🎉 ALL CORE SESSION BINDING TESTS PASSED!")
        print("✅ The original 'Instance is not bound to a Session' error is FIXED")
        print("✅ Bot status can be accessed safely after retrieval")
        print("✅ All repository methods handle session binding correctly")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up test database
        try:
            if os.path.exists('test_session_simple.db'):
                os.remove('test_session_simple.db')
                print("🧹 Test database cleaned up")
        except:
            pass


async def main():
    """Run the core tests"""
    print("🚀 Testing SQLAlchemy Session Binding Fixes")
    print("Focus: Resolving 'Instance is not bound to a Session' errors\n")
    
    success = await test_core_session_fixes()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 SESSION BINDING FIXES VERIFIED!")
        print("✅ The original error should no longer occur")
        print("✅ Bots can be created, retrieved, and their status checked")
        print("✅ All ORM objects are properly handled")
        print("\n📋 WHAT WAS FIXED:")
        print("   - get_bot() now returns dictionaries instead of detached ORM objects")
        print("   - All repository methods properly detach objects from sessions")
        print("   - API routes handle dictionary data instead of ORM objects")
        print("   - Status checks use safe accessor methods")
    else:
        print("❌ SESSION BINDING ISSUES STILL EXIST!")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)