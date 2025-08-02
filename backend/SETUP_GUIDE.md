# Backend Setup Guide

## Problem
The backend was failing to start because the `ccxt` module (and potentially other dependencies) weren't being found, even though they were installed.

## Root Cause
The backend needs to be run within the activated virtual environment to access all installed dependencies. Running Python directly without activating the virtual environment causes import errors.

## Solution

### 1. Verify Setup
The project is already properly configured:
- ✅ Virtual environment exists at `backend/venv/`
- ✅ All dependencies are installed (including `ccxt==4.1.22`)
- ✅ Requirements.txt is complete and up-to-date
- ✅ Environment files are configured in the project root

### 2. Proper Startup Methods

#### Method 1: Use the Startup Script (Recommended)
```bash
cd backend
./start_backend.sh
```

#### Method 2: Manual Activation
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

#### Method 3: One-liner
```bash
cd backend && source venv/bin/activate && uvicorn app.main:app --reload
```

### 3. If You Need to Reinstall
If there are still issues, run the setup script:
```bash
cd backend
./setup_backend.sh
```

## Verification

### Check Dependencies are Available
```bash
cd backend
source venv/bin/activate
python -c "import ccxt; print('ccxt version:', ccxt.__version__)"
```

### Check All Critical Imports
```bash
cd backend
source venv/bin/activate
python -c "
import ccxt, fastapi, pandas, numpy, sqlalchemy, uvicorn
print('All dependencies available!')
"
```

### Test Backend Import
```bash
cd backend
source venv/bin/activate
python -c "from app.main import app; print('Backend ready!')"
```

## Environment Configuration

The backend uses environment variables from:
1. `/Users/ArijinalBeat/Desktop/analytical-punch/.env.personal` (first priority)
2. `/Users/ArijinalBeat/Desktop/analytical-punch/.env` (fallback)

Current configuration:
- **PERSONAL_MODE**: true (unlimited features)
- **DATABASE_URL**: postgresql://postgres:postgres@localhost:5432/analytical_punch
- **REDIS_URL**: redis://localhost:6379
- **DEBUG**: true

## Access Points

Once started successfully:
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health (if available)

## Common Issues

### ImportError: No module named 'ccxt'
**Cause**: Virtual environment not activated
**Solution**: Always use `source venv/bin/activate` before running Python commands

### Port Already in Use
**Cause**: Another process is using port 8000
**Solution**: 
- Kill existing process: `lsof -ti:8000 | xargs kill`
- Or use different port: `uvicorn app.main:app --port 8001`

### Database Connection Errors
**Cause**: PostgreSQL not running
**Solution**: Start PostgreSQL or use Docker:
```bash
docker-compose up -d db  # If using Docker setup
```

## Files Created

1. **`start_backend.sh`**: Automated startup script with environment validation
2. **`setup_backend.sh`**: Complete setup script for fresh installations
3. **`SETUP_GUIDE.md`**: This documentation (you're reading it!)

## Next Steps

1. Start the backend using one of the methods above
2. Verify it's working by visiting http://localhost:8000/docs
3. Test API endpoints using the interactive documentation
4. If everything works, you can also start the frontend to have the complete system running

## Technical Details

- **Python Version**: 3.9
- **Virtual Environment**: `venv/` (standard Python venv)
- **Total Dependencies**: 20+ packages including FastAPI, ccxt, pandas, etc.
- **Package Manager**: pip
- **Server**: uvicorn (ASGI server)

This setup follows the standard Python development practices and matches the project's README.md instructions exactly.