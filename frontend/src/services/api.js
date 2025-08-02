import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

// Create axios instance
const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
axiosInstance.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
axiosInstance.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      // Server responded with error
      const errorMessage = error.response.data?.detail || error.response.data?.message || 'Server error';
      throw new Error(errorMessage);
    } else if (error.request) {
      // Request made but no response
      throw new Error('Network error - server unreachable');
    } else {
      // Something else happened
      throw new Error('An unexpected error occurred');
    }
  }
);

const api = {
  // Chart endpoints
  getChartData: async (symbol, interval = '1h', indicators = []) => {
    const params = new URLSearchParams({
      interval,
      ...(indicators.length > 0 && { indicators: indicators.join(',') })
    });
    
    return axiosInstance.get(`/chart/${symbol}?${params}`);
  },

  getAvailableIndicators: async (symbol) => {
    return axiosInstance.get(`/chart/${symbol}/indicators`);
  },

  getSignals: async (symbol, timeframe = '1h') => {
    return axiosInstance.get(`/chart/${symbol}/signals`, { params: { timeframe } });
  },

  // Market endpoints
  getAvailableSymbols: async (source = null) => {
    const params = source ? { source } : {};
    const response = await axiosInstance.get('/market/symbols', { params });
    
    // Flatten symbols from all sources
    if (response.sources) {
      const allSymbols = [];
      Object.entries(response.sources).forEach(([source, symbols]) => {
        symbols.forEach(symbol => {
          allSymbols.push({
            value: symbol,
            label: symbol,
            source: source
          });
        });
      });
      return allSymbols;
    }
    
    return response.symbols.map(s => ({ value: s, label: s, source }));
  },

  searchSymbols: async (query, limit = 10) => {
    return axiosInstance.get('/market/search', { params: { query, limit } });
  },

  getMarketInfo: async (symbol, source = null) => {
    const params = source ? { source } : {};
    return axiosInstance.get(`/market/info/${symbol}`, { params });
  },

  getTicker: async (symbol, source = null) => {
    const params = source ? { source } : {};
    return axiosInstance.get(`/market/ticker/${symbol}`, { params });
  },

  compareSymbols: async (symbols, timeframe = '1d', metric = 'performance') => {
    return axiosInstance.get('/market/compare', {
      params: { symbols, timeframe, metric }
    });
  },

  getTrendingSymbols: async (source = 'binance', metric = 'volume', limit = 10) => {
    return axiosInstance.get('/market/trending', {
      params: { source, metric, limit }
    });
  },

  // Backtest endpoints
  runBacktest: async (backtestConfig) => {
    return axiosInstance.post('/backtest/run', backtestConfig);
  },

  getBacktestStrategies: async () => {
    return axiosInstance.get('/backtest/strategies');
  },

  optimizeStrategy: async (optimizationConfig) => {
    return axiosInstance.post('/backtest/optimize', optimizationConfig);
  },

  getBacktestResults: async (backtestId) => {
    return axiosInstance.get(`/backtest/results/${backtestId}`);
  },

  getBacktestHistory: async (limit = 10) => {
    return axiosInstance.get('/backtest/history', { params: { limit } });
  },

  compareStrategies: async (comparisonConfig) => {
    return axiosInstance.post('/backtest/compare', comparisonConfig);
  },

  // Trading Bot endpoints
  getBots: async (activeOnly = false) => {
    return axiosInstance.get('/trading/bots', { params: { active_only: activeOnly } });
  },

  getBot: async (botId) => {
    return axiosInstance.get(`/trading/bots/${botId}`);
  },

  createBot: async (botConfig) => {
    return axiosInstance.post('/trading/bots', botConfig);
  },

  updateBot: async (botId, updates) => {
    return axiosInstance.put(`/trading/bots/${botId}`, updates);
  },

  deleteBot: async (botId) => {
    return axiosInstance.delete(`/trading/bots/${botId}`);
  },

  startBot: async (botId) => {
    return axiosInstance.post(`/trading/bots/${botId}/start`);
  },

  stopBot: async (botId) => {
    return axiosInstance.post(`/trading/bots/${botId}/stop`);
  },

  pauseBot: async (botId) => {
    return axiosInstance.post(`/trading/bots/${botId}/pause`);
  },

  resumeBot: async (botId) => {
    return axiosInstance.post(`/trading/bots/${botId}/resume`);
  },

  getBotPositions: async (botId) => {
    return axiosInstance.get(`/trading/bots/${botId}/positions`);
  },

  getBotTrades: async (botId, limit = 100, strategy = null) => {
    const params = { limit };
    if (strategy) params.strategy = strategy;
    return axiosInstance.get(`/trading/bots/${botId}/trades`, { params });
  },

  getBotOrders: async (botId, activeOnly = false, limit = 100) => {
    return axiosInstance.get(`/trading/bots/${botId}/orders`, {
      params: { active_only: activeOnly, limit }
    });
  },

  getBotPerformance: async (botId) => {
    return axiosInstance.get(`/trading/bots/${botId}/performance`);
  },

  // Alert endpoints
  getAlerts: async (botId = null, level = null, unacknowledgedOnly = false, limit = 100) => {
    const params = { limit, unacknowledged_only: unacknowledgedOnly };
    if (botId) params.bot_id = botId;
    if (level) params.level = level;
    return axiosInstance.get('/trading/alerts', { params });
  },

  acknowledgeAlert: async (alertId, acknowledgedBy = 'user') => {
    return axiosInstance.post(`/trading/alerts/${alertId}/acknowledge`, {
      acknowledged_by: acknowledgedBy
    });
  },

  // System endpoints
  getSystemStatus: async () => {
    return axiosInstance.get('/trading/system/status');
  },

  getSafetyStatus: async () => {
    return axiosInstance.get('/trading/safety/status');
  },

  // Health check
  healthCheck: async () => {
    return axiosInstance.get('/health');
  }
};

export default api;