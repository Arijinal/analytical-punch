#!/usr/bin/env python3
"""
Backend Setup Verification Script
Tests all critical dependencies and configurations
"""

import sys

def main():
    print("=== Final Verification ===")
    print(f"Python executable: {sys.executable}")
    print(f"Virtual env active: {sys.prefix != sys.base_prefix}")
    
    print("\n=== Testing Critical Imports ===")
    
    # Test ccxt
    try:
        import ccxt
        print(f"✅ ccxt: {ccxt.__version__}")
    except ImportError as e:
        print(f"❌ ccxt: {e}")
        return False
    
    # Test FastAPI
    try:
        import fastapi
        print(f"✅ fastapi: {fastapi.__version__}")
    except ImportError as e:
        print(f"❌ fastapi: {e}")
        return False
    
    # Test pandas
    try:
        import pandas
        print(f"✅ pandas: {pandas.__version__}")
    except ImportError as e:
        print(f"❌ pandas: {e}")
        return False
    
    # Test SQLAlchemy
    try:
        import sqlalchemy
        print(f"✅ sqlalchemy: {sqlalchemy.__version__}")
    except ImportError as e:
        print(f"❌ sqlalchemy: {e}")
        return False
    
    # Test uvicorn
    try:
        import uvicorn
        print(f"✅ uvicorn: {uvicorn.__version__}")
    except ImportError as e:
        print(f"❌ uvicorn: {e}")
        return False
    
    print("\n=== Testing Backend Import ===")
    try:
        from app.main import app
        print("✅ Backend app imported successfully")
    except ImportError as e:
        print(f"❌ Backend import failed: {e}")
        return False
    
    print("\n=== Configuration Test ===")
    try:
        from app.config import get_config
        config = get_config()
        print(f"✅ Config loaded - Personal Mode: {config.PERSONAL_MODE}")
        print(f"✅ Available sources: {config.AVAILABLE_SOURCES}")
    except Exception as e:
        print(f"❌ Config error: {e}")
        return False
    
    print("\n🎉 All tests passed! Backend is ready to start.")
    print("\nTo start the backend:")
    print("  ./start_backend.sh")
    print("  or")
    print("  source venv/bin/activate && uvicorn app.main:app --reload")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)