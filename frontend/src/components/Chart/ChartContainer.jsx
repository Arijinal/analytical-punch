import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';
import { useChartStore } from '../../store/chartStore';
import Indicators from './Indicators';
import './Chart.css';

const ChartContainer = () => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candlestickSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  
  const { 
    chartData, 
    indicators, 
    selectedIndicators,
    selectedSymbol,
    selectedTimeframe,
    fetchChartData,
    isLoading,
    error
  } = useChartStore();

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: 'solid', color: '#0a0a0a' },
        textColor: '#a0a0a0',
      },
      grid: {
        vertLines: { color: '#1e1e1e' },
        horzLines: { color: '#1e1e1e' },
      },
      crosshair: {
        mode: 1, // Magnet mode
        vertLine: {
          color: '#00d4ff',
          width: 1,
          style: 2,
          labelBackgroundColor: '#00d4ff',
        },
        horzLine: {
          color: '#00d4ff',
          width: 1,
          style: 2,
          labelBackgroundColor: '#00d4ff',
        },
      },
      rightPriceScale: {
        borderColor: '#2a2a2a',
        scaleMargins: {
          top: 0.1,
          bottom: 0.25,
        },
      },
      timeScale: {
        borderColor: '#2a2a2a',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // Create candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#00ff88',
      downColor: '#ff3366',
      borderUpColor: '#00ff88',
      borderDownColor: '#ff3366',
      wickUpColor: '#00ff88',
      wickDownColor: '#ff3366',
    });

    // Create volume series
    const volumeSeries = chart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '',
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    chartRef.current = chart;
    candlestickSeriesRef.current = candlestickSeries;
    volumeSeriesRef.current = volumeSeries;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chart) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chart) {
        try {
          chart.remove();
        } catch (error) {
          console.debug('Chart already removed or disposed');
        }
      }
    };
  }, []);

  // Update chart data
  useEffect(() => {
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current || !chartData) return;

    console.log('Chart data received:', chartData);
    console.log('First candle:', chartData[0]);

    // Validate and format data for lightweight charts
    const validCandles = chartData.filter(candle => {
      const isValid = candle && 
        candle.time !== undefined && 
        candle.open !== undefined && 
        candle.high !== undefined && 
        candle.low !== undefined && 
        candle.close !== undefined && 
        candle.volume !== undefined;
      
      if (!isValid && candle) {
        console.warn('Invalid candle data:', candle);
      }
      
      return isValid;
    });

    if (validCandles.length === 0) {
      console.warn('No valid candle data to display');
      return;
    }

    try {
      const formattedCandles = validCandles.map(candle => ({
        time: candle.time,
        open: Number(candle.open),
        high: Number(candle.high),
        low: Number(candle.low),
        close: Number(candle.close),
      }));

      const formattedVolume = validCandles.map(candle => ({
        time: candle.time,
        value: Number(candle.volume),
        color: Number(candle.close) >= Number(candle.open) ? '#00ff8833' : '#ff336633',
      }));

      candlestickSeriesRef.current.setData(formattedCandles);
      volumeSeriesRef.current.setData(formattedVolume);

      // Fit content
      if (chartRef.current) {
        chartRef.current.timeScale().fitContent();
      }
    } catch (error) {
      console.error('Error setting chart data:', error);
    }
  }, [chartData]);

  // Fetch initial data
  useEffect(() => {
    fetchChartData();
  }, []);

  // Show loading state
  if (isLoading && !chartData) {
    return (
      <div className="chart-container">
        <div className="chart-loading">
          <div className="loading-spinner"></div>
          <p>Loading chart data...</p>
        </div>
      </div>
    );
  }

  // Show error state
  if (error && !chartData) {
    return (
      <div className="chart-container">
        <div className="chart-error">
          <p>Error loading chart data: {error}</p>
          <button onClick={fetchChartData}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="chart-container">
      <div className="chart-header">
        <div className="chart-info">
          <h2 className="chart-title">{selectedSymbol}</h2>
          <span className="chart-timeframe">{selectedTimeframe}</span>
        </div>
        
        <div className="chart-stats">
          {chartData && Array.isArray(chartData) && chartData.length > 0 && chartData[chartData.length - 1] && (
            <>
              <div className="stat">
                <span className="stat-label">Last:</span>
                <span className="stat-value">
                  ${chartData[chartData.length - 1].close !== undefined && chartData[chartData.length - 1].close !== null
                    ? Number(chartData[chartData.length - 1].close).toFixed(2) 
                    : '0.00'}
                </span>
              </div>
              <div className="stat">
                <span className="stat-label">Change:</span>
                <span className={`stat-value ${
                  chartData.length >= 2 && 
                  chartData[chartData.length - 1]?.close !== undefined && 
                  chartData[chartData.length - 2]?.close !== undefined &&
                  Number(chartData[chartData.length - 1].close) >= Number(chartData[chartData.length - 2].close)
                    ? 'positive' : 'negative'
                }`}>
                  {chartData.length >= 2 && 
                   chartData[0]?.close !== undefined && 
                   chartData[0]?.close !== null &&
                   chartData[chartData.length - 1]?.close !== undefined &&
                   chartData[chartData.length - 1]?.close !== null
                    ? ((Number(chartData[chartData.length - 1].close) - Number(chartData[0].close)) / Number(chartData[0].close) * 100).toFixed(2)
                    : '0.00'}%
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="chart-wrapper">
        <div ref={chartContainerRef} className="chart-canvas" />
        
        {/* Overlay indicators */}
        {chartRef.current && (
          <Indicators 
            chart={chartRef.current}
            indicators={indicators}
            selectedIndicators={selectedIndicators}
          />
        )}
      </div>

      <div className="chart-controls">
        <div className="indicator-toggles">
          {['sma', 'ema', 'bollinger_bands', 'rsi', 'macd'].map(indicator => (
            <button
              key={indicator}
              className={`indicator-toggle ${selectedIndicators.includes(indicator) ? 'active' : ''}`}
              onClick={() => useChartStore.getState().toggleIndicator(indicator)}
            >
              {indicator.toUpperCase().replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ChartContainer;