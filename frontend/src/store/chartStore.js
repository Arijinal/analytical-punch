import { create } from 'zustand';
import api from '../services/api';
import toast from 'react-hot-toast';

const useChartStore = create((set, get) => ({
  // State
  selectedSymbol: 'BTC/USDT',
  selectedTimeframe: '1h',
  chartData: null,
  indicators: {},
  signals: [],
  marketInfo: null,
  isLoading: false,
  error: null,
  
  // Available options
  availableSymbols: [],
  availableIndicators: [],
  selectedIndicators: ['sma', 'rsi', 'macd'],
  
  // Actions
  setSymbol: (symbol) => {
    set({ selectedSymbol: symbol });
    get().fetchChartData();
  },
  
  setTimeframe: (timeframe) => {
    set({ selectedTimeframe: timeframe });
    get().fetchChartData();
  },
  
  toggleIndicator: (indicatorName) => {
    const current = get().selectedIndicators;
    const updated = current.includes(indicatorName)
      ? current.filter(i => i !== indicatorName)
      : [...current, indicatorName];
    
    set({ selectedIndicators: updated });
    get().fetchChartData();
  },
  
  fetchChartData: async () => {
    const { selectedSymbol, selectedTimeframe, selectedIndicators } = get();
    
    set({ isLoading: true, error: null });
    
    try {
      const response = await api.getChartData(
        selectedSymbol,
        selectedTimeframe,
        selectedIndicators
      );
      
      set({
        chartData: response.candles,
        indicators: response.indicators,
        signals: response.signals,
        marketInfo: response.market_info,
        isLoading: false,
        error: null
      });
      
    } catch (error) {
      console.error('Error fetching chart data:', error);
      set({
        isLoading: false,
        error: error.message || 'Failed to fetch chart data'
      });
      toast.error('Failed to load chart data');
    }
  },
  
  fetchAvailableSymbols: async () => {
    try {
      const symbols = await api.getAvailableSymbols();
      set({ availableSymbols: symbols });
    } catch (error) {
      console.error('Error fetching symbols:', error);
    }
  },
  
  fetchAvailableIndicators: async () => {
    try {
      const { selectedSymbol } = get();
      const indicators = await api.getAvailableIndicators(selectedSymbol);
      set({ availableIndicators: indicators });
    } catch (error) {
      console.error('Error fetching indicators:', error);
    }
  },
  
  // WebSocket updates
  updatePrice: (symbol, priceData) => {
    if (symbol !== get().selectedSymbol) return;
    
    const chartData = get().chartData;
    if (!chartData || chartData.length === 0) return;
    
    // Update the last candle
    const updatedData = [...chartData];
    const lastCandle = { ...updatedData[updatedData.length - 1] };
    
    lastCandle.close = priceData.price;
    lastCandle.high = Math.max(lastCandle.high, priceData.price);
    lastCandle.low = Math.min(lastCandle.low, priceData.price);
    lastCandle.volume = priceData.volume || lastCandle.volume;
    
    updatedData[updatedData.length - 1] = lastCandle;
    
    set({ chartData: updatedData });
  },
  
  updateIndicator: (symbol, indicatorName, data) => {
    if (symbol !== get().selectedSymbol) return;
    
    set(state => ({
      indicators: {
        ...state.indicators,
        [indicatorName]: data
      }
    }));
  },
  
  addSignal: (symbol, signal) => {
    if (symbol !== get().selectedSymbol) return;
    
    set(state => ({
      signals: [signal, ...state.signals].slice(0, 10) // Keep last 10 signals
    }));
    
    // Show notification for high confidence signals
    if (signal.confidence > 0.7) {
      toast.success(
        `${signal.strategy}: ${signal.direction.toUpperCase()} signal`,
        {
          duration: 5000,
          icon: signal.direction === 'buy' ? '📈' : '📉'
        }
      );
    }
  }
}));

export { useChartStore };