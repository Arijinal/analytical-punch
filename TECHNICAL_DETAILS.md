# Analytical Punch - Technical Implementation Details

## 🔧 Architecture Deep Dive

### System Architecture
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  React Frontend │────▶│  FastAPI Backend│────▶│  Data Sources   │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Zustand Store  │     │   PostgreSQL    │     │ CoinGecko/Kraken│
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Data Flow Architecture
```
User Request → API Gateway → Route Handler → Business Logic
                                    ↓
                            Data Manager → Source Selection
                                    ↓
                            Symbol Normalizer → API Request
                                    ↓
                            Data Processing → Indicators
                                    ↓
                            Response Serialization → JSON Response
```

---

## 💾 Database Schema

### Core Tables
```sql
-- Users (for SaaS mode)
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Trading Bots
CREATE TABLE trading_bots (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    strategy JSONB NOT NULL,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Trades
CREATE TABLE trades (
    id UUID PRIMARY KEY,
    bot_id UUID REFERENCES trading_bots(id),
    symbol VARCHAR(50),
    side VARCHAR(10),
    quantity DECIMAL,
    price DECIMAL,
    executed_at TIMESTAMP
);

-- Performance Metrics
CREATE TABLE performance_metrics (
    id UUID PRIMARY KEY,
    bot_id UUID REFERENCES trading_bots(id),
    metric_type VARCHAR(50),
    value DECIMAL,
    calculated_at TIMESTAMP
);
```

---

## 🔌 API Endpoints Documentation

### Chart Data Endpoints
```
GET /api/v1/chart/{symbol}
├── Parameters:
│   ├── symbol: Trading pair (e.g., BTC-USD)
│   ├── interval: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)
│   ├── indicators: Comma-separated list
│   └── limit: Number of candles
└── Response: {
    candles: Array<OHLCV>,
    indicators: Object,
    signals: Array<Signal>,
    market_info: Object
}
```

### Market Data Endpoints
```
GET /api/v1/market/symbols
GET /api/v1/market/ticker/{symbol}
GET /api/v1/market/info/{symbol}
GET /api/v1/market/compare
GET /api/v1/market/trending
```

### Trading Bot Endpoints
```
POST /api/v1/bots/create
GET /api/v1/bots/list
PUT /api/v1/bots/{bot_id}/start
PUT /api/v1/bots/{bot_id}/stop
GET /api/v1/bots/{bot_id}/performance
```

### WebSocket Endpoints
```
WS /ws
├── Subscribe: {"action": "subscribe", "symbol": "BTC-USD", "interval": "1m"}
├── Unsubscribe: {"action": "unsubscribe", "symbol": "BTC-USD"}
└── Receive: {
    "type": "price_update" | "indicator_update" | "signal",
    "data": {...}
}
```

---

## 🧮 Technical Indicators Implementation

### 1. Simple Moving Average (SMA)
```python
def calculate(self, data: pd.DataFrame) -> IndicatorResult:
    closes = data['close']
    sma_values = {}
    
    for period in self.periods:
        sma_values[f'sma_{period}'] = closes.rolling(window=period).mean()
    
    primary_sma = sma_values[f'sma_{self.periods[0]}']
    return IndicatorResult(
        name='sma',
        values=primary_sma,
        params={'periods': self.periods},
        additional=sma_values
    )
```

### 2. RSI (Relative Strength Index)
```python
def calculate(self, data: pd.DataFrame) -> IndicatorResult:
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    signals = pd.Series(0, index=data.index)
    signals[rsi < self.oversold] = 1  # Buy signal
    signals[rsi > self.overbought] = -1  # Sell signal
```

### 3. MACD (Moving Average Convergence Divergence)
```python
def calculate(self, data: pd.DataFrame) -> IndicatorResult:
    exp1 = data['close'].ewm(span=self.fast_period, adjust=False).mean()
    exp2 = data['close'].ewm(span=self.slow_period, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
```

---

## 🔄 Data Source Integration Details

### Symbol Normalization Flow
```python
# Frontend sends: BTC/USDT
# Normalizer converts to: BTC-USD
# CoinGecko needs: bitcoin
# Kraken needs: XBTUSD
# Coinbase needs: BTC-USD

def convert_for_source(symbol: str, source: str) -> str:
    normalized = self.normalize_symbol(symbol)  # BTC-USD
    if source == 'coingecko':
        return self.coingecko_map[normalized]  # bitcoin
    elif source == 'kraken':
        return self.kraken_map[normalized]     # XBTUSD
    elif source == 'coinbase':
        return normalized                       # BTC-USD
```

### Fallback Logic Implementation
```python
async def fetch_ohlcv(self, symbol: str, ...) -> pd.DataFrame:
    # Try primary source
    source = self.get_source(symbol)
    try:
        return await source.fetch_ohlcv(symbol, ...)
    except Exception as e:
        logger.error(f"Primary source failed: {e}")
        
        # Try fallback sources in priority order
        for fallback in ['coingecko', 'kraken', 'coinbase']:
            if fallback != source.name and fallback in self.sources:
                try:
                    return await self.sources[fallback].fetch_ohlcv(...)
                except:
                    continue
        raise
```

---

## 🚀 Performance Optimizations

### 1. Caching Strategy
```python
@cached(ttl=300)  # 5-minute cache
async def fetch_ohlcv(self, symbol: str, timeframe: str):
    # Expensive API call cached
    return await self._fetch_from_api(symbol, timeframe)
```

### 2. Batch Processing
```python
async def calculate_all_indicators(self, data: pd.DataFrame):
    tasks = []
    for indicator in self.indicators:
        tasks.append(indicator.calculate_async(data))
    results = await asyncio.gather(*tasks)
    return results
```

### 3. WebSocket Connection Pooling
```python
class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)
    
    async def subscribe(self, websocket: WebSocket, symbol: str):
        client_id = id(websocket)
        self.connections[client_id] = websocket
        self.subscriptions[symbol].add(client_id)
```

---

## 🛠️ Error Handling Patterns

### 1. Graceful Degradation
```python
try:
    data = await self.fetch_from_primary_source()
except PrimarySourceError:
    try:
        data = await self.fetch_from_secondary_source()
    except SecondarySourceError:
        data = await self.fetch_from_cache()
        logger.warning("Using cached data")
```

### 2. Circuit Breaker Pattern
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
```

### 3. Retry with Exponential Backoff
```python
async def fetch_with_retry(self, func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # Exponential backoff
            await asyncio.sleep(wait_time)
```

---

## 🔐 Security Implementations

### 1. Input Validation
```python
@router.get("/chart/{symbol}")
async def get_chart_data(
    symbol: str = Path(..., regex="^[A-Z0-9-/]+$"),
    interval: str = Query(..., regex="^(1m|5m|15m|30m|1h|4h|1d)$")
):
    # Validated inputs only
```

### 2. Rate Limiting
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@router.get("/api/v1/chart/{symbol}")
@limiter.limit("60/minute")
async def get_chart_data(request: Request, symbol: str):
    # Rate limited endpoint
```

### 3. API Key Authentication
```python
async def verify_api_key(api_key: str = Header(...)):
    if not await is_valid_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key
```

---

## 📊 Monitoring & Logging

### 1. Structured Logging
```python
logger = setup_logger(__name__)
logger.info("Data fetched", extra={
    "symbol": symbol,
    "source": source_name,
    "latency_ms": latency,
    "candle_count": len(data)
})
```

### 2. Performance Metrics
```python
class PerformanceMonitor:
    async def track_api_call(self, endpoint: str, duration: float):
        await self.redis.hincrby(f"api_calls:{endpoint}", "count", 1)
        await self.redis.hincrbyfloat(f"api_calls:{endpoint}", "total_time", duration)
```

### 3. Health Checks
```python
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "services": {
            "database": await check_db_connection(),
            "redis": await check_redis_connection(),
            "data_sources": await check_data_sources()
        }
    }
```

---

## 🧪 Testing Strategy

### 1. Unit Tests
```python
async def test_sma_calculation():
    data = create_test_data()
    indicator = SMAIndicator(periods=[20, 50])
    result = await indicator.calculate(data)
    assert len(result.values) == len(data)
    assert not result.values[:19].notna().any()  # First 19 should be NaN
```

### 2. Integration Tests
```python
async def test_data_source_fallback():
    manager = DataManager()
    with mock.patch('primary_source.fetch_ohlcv', side_effect=Exception):
        data = await manager.fetch_ohlcv('BTC-USD', '1h')
        assert data.attrs['source'] == 'coingecko'  # Fallback source
```

### 3. End-to-End Tests
```python
async def test_full_chart_flow():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/chart/BTC-USD?interval=1h")
        assert response.status_code == 200
        data = response.json()
        assert 'candles' in data
        assert 'indicators' in data
        assert len(data['candles']) > 0
```

---

## 🔧 Deployment Considerations

### 1. Environment Variables
```bash
# Production .env
DATABASE_URL=postgresql://user:pass@db:5432/analytical_punch
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=https://analytical-punch.com
LOG_LEVEL=INFO
SENTRY_DSN=https://...
```

### 2. Docker Composition
```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    environment:
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - db
      - redis
  
  frontend:
    build: ./frontend
    environment:
      - REACT_APP_API_URL=${API_URL}
  
  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "80:80"
      - "443:443"
```

### 3. Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: analytical-punch-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    spec:
      containers:
      - name: backend
        image: analytical-punch/backend:latest
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

---

*This technical documentation provides deep implementation details for maintaining and extending Analytical Punch.*