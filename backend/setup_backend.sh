#!/bin/bash

# Backend Setup Script
# Sets up the virtual environment and installs dependencies

set -e  # Exit on any error

echo "Setting up Analytical Punch Backend..."

# Check if we're in the backend directory
if [ ! -f "requirements.txt" ]; then
    echo "Error: This script must be run from the backend directory"
    echo "Current directory: $(pwd)"
    echo "Please run: cd backend && ./setup_backend.sh"
    exit 1
fi

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1)
echo "Found: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Verify installation
echo "Verifying installation..."
echo "Installed packages:"
pip list --format=columns | grep -E "(ccxt|fastapi|pandas|numpy|sqlalchemy|uvicorn)"

# Test imports
echo ""
echo "Testing critical imports..."
python -c "
import ccxt
import fastapi
import pandas
import numpy
import sqlalchemy
import uvicorn
print('✓ All critical dependencies imported successfully')
"

echo ""
echo "Setup complete! 🎉"
echo ""
echo "To start the backend:"
echo "  ./start_backend.sh"
echo ""
echo "Or manually:"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload"