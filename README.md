# Analytical Punch - Professional Trading Analysis Platform

A comprehensive financial analysis platform with technical indicators, signal generation, and backtesting capabilities. Runs locally first with the ability to scale to SaaS later.

## Features

### 🎯 Core Capabilities
- **Real-time Chart Analysis**: OHLCV data with multiple timeframes
- **12+ Technical Indicators**: SMA, EMA, RSI, MACD, Bollinger Bands, Ichimoku Cloud, and more
- **4 Punch Trading Strategies**: 
  - Momentum Punch (trend following)
  - Value Punch (mean reversion)
  - Breakout Punch (volatility expansion)
  - Trend Punch (strong directional moves)
- **Advanced Backtesting**: Event-driven engine with comprehensive metrics
- **Multi-Source Data**: Binance (crypto), Yahoo Finance (stocks), CSV import
- **WebSocket Real-time Updates**: Live price and indicator updates

### 🔓 Personal Mode Features
When `PERSONAL_MODE=true`:
- Unlimited indicators
- 10 years of historical data
- ML-powered signals
- Usage tracking and analytics
- Trade journal
- No rate limits

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)

### Running with Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd analytical-punch
```

2. Copy environment files:
```bash
cp .env.example .env
# For personal mode with all features:
cp .env.personal .env
```

3. Start the platform:
```bash
docker-compose up -d
```

4. Access the platform:
- Frontend: http://localhost:3000
- API Documentation: http://localhost:8000/docs
- pgAdmin: http://localhost:5050 (admin@analytical.punch / admin123)

### Local Development

#### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### Frontend Setup
```bash
cd frontend
npm install
npm start
```

## Architecture

### Backend (FastAPI)
```
backend/
├── app/
│   ├── api/          # REST endpoints & WebSocket
│   ├── core/         # Business logic
│   │   ├── indicators/    # Technical indicators
│   │   ├── signals/       # Trading signals
│   │   └── backtest/      # Backtesting engine
│   ├── data/         # Data sources
│   └── utils/        # Utilities (cache, logging)
```

### Frontend (React)
```
frontend/
├── src/
│   ├── components/   # UI components
│   ├── hooks/        # Custom React hooks
│   ├── services/     # API client
│   └── store/        # State management (Zustand)
```

## API Endpoints

### Core Endpoints
- `GET /api/v1/chart/{symbol}` - Get OHLCV data with indicators and signals
- `GET /api/v1/market/symbols` - List available symbols
- `POST /api/v1/backtest/run` - Run backtest
- `WS /ws` - WebSocket for real-time updates

### Example Request
```bash
curl http://localhost:8000/api/v1/chart/BTC-USDT?interval=1h&indicators=sma,rsi,macd
```

## Configuration

### Environment Variables
- `PERSONAL_MODE`: Enable all features (true/false)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `BINANCE_API_KEY`: Optional Binance API key
- `BINANCE_API_SECRET`: Optional Binance API secret

### Indicator Configuration
Modify `backend/app/config.py` to adjust default indicator parameters:
```python
INDICATOR_DEFAULTS = {
    'sma': {'periods': [20, 50, 200]},
    'rsi': {'period': 14, 'overbought': 70, 'oversold': 30},
    # ... more indicators
}
```

## Data Sources

### Binance (Crypto)
- No API key required for public data
- Real-time price updates
- All major crypto pairs

### Yahoo Finance (Stocks)
- US stocks, ETFs, indices
- 1-minute to monthly timeframes
- Company fundamentals

### CSV Import
- Custom data for backtesting
- Place CSV files in `backend/data/csv/`
- Format: Date, Open, High, Low, Close, Volume

## Trading Strategies

### Momentum Punch
- Trend following with momentum confirmation
- Uses RSI, MACD, and EMA alignment
- Best for trending markets

### Value Punch
- Mean reversion at extremes
- Uses RSI oversold/overbought with Bollinger Bands
- Best for ranging markets

### Breakout Punch
- Volatility expansion trades
- Bollinger Band squeeze release
- Support/resistance breakouts

### Trend Punch
- Strong directional moves
- Ichimoku Cloud with SMA alignment
- Multi-timeframe confirmation

## Backtesting

### Running a Backtest
1. Select symbol and strategy
2. Set date range and parameters
3. Click "Run Backtest"
4. View results including:
   - Equity curve
   - Performance metrics
   - Trade log
   - Risk statistics

### Key Metrics
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / gross loss

## Development

### Adding a New Indicator
1. Create indicator class in `backend/app/core/indicators/`
2. Inherit from `Indicator` base class
3. Implement `calculate()` method
4. Register in `IndicatorManager`

### Adding a New Strategy
1. Add strategy method in `backend/app/core/signals/generator.py`
2. Implement signal logic
3. Add to strategies dictionary
4. Update frontend if needed

## Performance Optimization

- 5-minute Redis caching for API responses
- WebSocket for real-time updates (no polling)
- Efficient pandas/numpy calculations
- Database connection pooling
- React component memoization

## Troubleshooting

### Common Issues

1. **Port conflicts**: Change ports in docker-compose.yml
2. **Memory issues**: Adjust Docker memory limits
3. **Data not loading**: Check data source connectivity
4. **WebSocket disconnects**: Check firewall/proxy settings

### Logs
- Backend logs: `docker logs analytical_punch_backend`
- Frontend logs: Browser console
- Database logs: `docker logs analytical_punch_db`

## Future Enhancements

- [ ] Machine learning price predictions
- [ ] Options chain analysis
- [ ] Social sentiment integration
- [ ] Mobile app
- [ ] Cloud deployment scripts
- [ ] Advanced order types
- [ ] Portfolio optimization

## License

This project is for personal/educational use. See LICENSE file for details.

## Support

For issues or questions:
1. Check the FAQ in docs/
2. Search existing GitHub issues
3. Create a new issue with details

---

Built with ❤️ for traders who want professional-grade tools without the enterprise price tag.