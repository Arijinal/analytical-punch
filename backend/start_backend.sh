#!/bin/bash

# Start Backend with Virtual Environment
# This ensures all dependencies are available

set -e  # Exit on any error

# Check if we're in the backend directory
if [ ! -f "requirements.txt" ]; then
    echo "Error: This script must be run from the backend directory"
    echo "Current directory: $(pwd)"
    echo "Please run: cd backend && ./start_backend.sh"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found"
    echo "Please run the setup first:"
    echo "  python -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Checking Python version..."
python --version

echo "Verifying key dependencies..."
python -c "import ccxt; print('✓ ccxt:', ccxt.__version__)" 2>/dev/null || echo "✗ ccxt not found"
python -c "import fastapi; print('✓ fastapi:', fastapi.__version__)" 2>/dev/null || echo "✗ fastapi not found"
python -c "import pandas; print('✓ pandas:', pandas.__version__)" 2>/dev/null || echo "✗ pandas not found"

echo "Starting backend server..."
echo "Access at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo "Press Ctrl+C to stop"

# Start the server with proper configuration
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload