# CLAUDE.md - Analytical Punch Project

## 🎯 PROJECT IDENTITY
**This is Analytical Punch - A Professional Trading Analysis Platform**
- **NOT** related to Arcadian Universal Separator in any way
- **Location**: `/Users/ArijinalBeat/Desktop/analytical-punch/`
- **GitHub**: https://github.com/Arijinal/analytical-punch.git
- **Purpose**: Comprehensive financial analysis with indicators, signals, backtesting, and automated trading bots

## 📊 CURRENT PROJECT STATUS (December 2024)

### ✅ Latest Accomplishments (Current Session)
1. **Fixed Trading Bot UI Display**
   - Resolved data structure mismatch between API and frontend
   - API returns array directly, frontend was expecting `{bots: []}`
   - Fixed in `TradingDashboard.jsx` line 28

2. **Bot Lifecycle Management Fixed**
   - Added STARTING status to BotStatus enum
   - All status updates now use proper enum values (not strings)
   - Bot restoration mechanism for server restarts implemented
   - Exchange connection fixed for paper trading

3. **Database Enum Handling**
   - Fixed all occurrences of string status values
   - Now using `BotStatus.RUNNING`, `BotStatus.STOPPED`, etc.
   - No more PostgreSQL enum type errors

### 🚀 Current Working Features
- **Charts**: Real-time OHLCV with 13 technical indicators
- **Trading Signals**: 4 Punch strategies generating live recommendations
- **Backtesting**: Full engine with comprehensive metrics
- **Data Sources**: Kraken, Coinbase, Yahoo Finance (CoinGecko rate limited)
- **WebSocket**: Real-time price and signal updates
- **Trading Bots**: Create, start, stop, pause, resume functionality
- **Paper Trading**: Works without API credentials

## 🔧 KEY FILES MODIFIED (Latest Session)

### Backend Changes:
1. **`/backend/app/models/trading.py`**
   ```python
   class BotStatus(Enum):
       STOPPED = "stopped"
       STARTING = "starting"  # Added this
       RUNNING = "running"
       PAUSED = "paused"
       ERROR = "error"
   ```

2. **`/backend/app/api/routes/trading.py`**
   - Added `from app.models.trading import BotStatus`
   - Fixed all status updates to use enums
   - Added `_restore_bot_from_database()` function
   - Fixed status comparisons

3. **`/backend/app/core/trading/exchange.py`**
   - Skip `load_markets()` for paper trading
   - Prevents "Service unavailable from restricted location" errors

### Frontend Changes:
1. **`/frontend/src/components/Trading/TradingDashboard.jsx`**
   - Fixed data structure handling (line 28)
   - Now handles both array and nested object formats
   - Bots display correctly in the UI

## 🏗️ ARCHITECTURE OVERVIEW

### Trading Bot Flow:
```
User creates bot → API creates DB entry → Bot instance created → Stored in active_bots
User starts bot → Status: STOPPED → STARTING → RUNNING → Main loop executes
Server restart → active_bots cleared → Bot restored from DB on next start request
```

### Main Components:
- **AdaptiveMultiStrategyBot**: Main bot class with 4 strategies
- **BinanceExchange**: Exchange integration (paper/live modes)
- **SafetyManager**: Risk management and kill switches
- **Bot Repository**: Database operations with proper enum handling

## ⚠️ IMPORTANT PATTERNS

### Always Use Enums for Status:
```python
# ❌ WRONG
bot_repository.update_bot(bot_id, {'status': 'running'})

# ✅ CORRECT
bot_repository.update_bot(bot_id, {'status': BotStatus.RUNNING})
```

### Frontend Data Structure:
```javascript
// API returns array directly
const botsData = await api.getBots();
// Handle both formats for compatibility
setBots(Array.isArray(botsData) ? botsData : botsData.bots || []);
```

### Paper Trading Connection:
```python
# Skip market loading for paper trading
if not self.paper_trading:
    await self.exchange.load_markets()
```

## 📝 TODO LIST STATUS

### ✅ Completed Tasks:
- All UI components (Charts, Indicators, Trading Bots, Backtest)
- Data source integrations (except CoinGecko hourly)
- Signal generation for all 4 strategies
- Bot lifecycle management with proper enum handling
- Frontend data structure fixes
- Exchange connection for paper trading

### 🔄 In Progress:
- **Bot Main Loop Verification**: Need to confirm continuous execution
- **Signal Generation in Bots**: Test that running bots generate and execute trades
- **Performance Metrics**: Real-time updates to bot statistics

### 📋 Pending Tasks:
1. **Database Configuration**: Currently expects PostgreSQL, may need SQLite option
2. **Bot State Persistence**: Verify save/restore functionality
3. **Live Trading Mode**: Test with real exchange credentials
4. **Performance Optimization**: Monitor bot resource usage
5. **Error Recovery**: Test bot behavior during network issues

## 🛠️ DEVELOPMENT SETUP

### Backend Dependencies Issue:
```bash
# If you see "No module named 'psycopg2'"
# The system is configured for PostgreSQL but might not have driver installed
# Consider adding SQLite fallback option
```

### Running the Application:
```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm start
```

## 🎯 NEXT IMMEDIATE STEPS

1. **Verify Bot Execution**:
   - Create a bot through UI
   - Start it and monitor logs
   - Confirm main loop runs continuously
   - Check if signals are being processed

2. **Test Signal Generation**:
   - Ensure running bots call strategy methods
   - Verify orders are placed (paper trading)
   - Check position management

3. **Database Options**:
   - Add SQLite support for easier local development
   - Make PostgreSQL optional

## 🔍 DEBUGGING TIPS

### Check Bot Status:
```python
# In Python console
from app.database.trading_db import bot_repository
bots = bot_repository.get_all_bots()
for bot in bots:
    print(f"{bot['name']}: {bot['status']}")
```

### Monitor Bot Logs:
```bash
# Watch for bot lifecycle events
tail -f backend/logs/trading.log | grep -E "(Starting|Started|Stopped|Error)"
```

### Test API Endpoints:
```bash
# Get all bots
curl http://localhost:8000/api/v1/trading/bots

# Start a bot
curl -X POST http://localhost:8000/api/v1/trading/bots/{bot_id}/start
```

## 📌 CRITICAL REMINDERS

1. **This is Analytical Punch** - Not Arcadian!
2. **Use Enums** - Never use string status values
3. **Test Paper Trading First** - Before enabling live trading
4. **Check Logs** - Bot events are logged extensively
5. **Frontend Expects Arrays** - Not nested objects for bot lists

---
*Last Updated: December 2024 - Bot Lifecycle Management Fully Functional*
*Next Focus: Verify continuous trading execution and signal processing*