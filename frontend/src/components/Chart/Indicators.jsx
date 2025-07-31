import React, { useEffect, useRef } from 'react';

const Indicators = ({ chart, indicators, selectedIndicators }) => {
  const indicatorSeriesRef = useRef({});
  const chartInstanceRef = useRef(null);

  useEffect(() => {
    if (!chart || !indicators) return;
    
    // Store the current chart instance
    chartInstanceRef.current = chart;

    // Function to safely remove a series
    const safeRemoveSeries = (seriesKey, series) => {
      try {
        // Check if series is valid and chart still exists
        if (series && chart && typeof chart.removeSeries === 'function') {
          chart.removeSeries(series);
        }
      } catch (error) {
        // Silently ignore - series was already removed
      }
    };

    // Clear existing indicator series
    const currentSeries = { ...indicatorSeriesRef.current };
    indicatorSeriesRef.current = {};
    
    Object.entries(currentSeries).forEach(([key, series]) => {
      safeRemoveSeries(key, series);
    });

    // Add selected indicators
    selectedIndicators.forEach(indicatorName => {
      const indicatorData = indicators[indicatorName];
      if (!indicatorData) return;

      switch (indicatorName) {
        case 'sma':
        case 'ema':
          // Add moving averages
          if (indicatorData.values && indicatorData.timestamps) {
            const series = chart.addLineSeries({
              color: indicatorName === 'sma' ? '#ffaa00' : '#00d4ff',
              lineWidth: 2,
              title: indicatorName.toUpperCase(),
              crosshairMarkerVisible: false,
            });

            const formattedData = indicatorData.values
              .map((value, index) => ({
                time: indicatorData.timestamps[index],
                value: value
              }))
              .filter(d => d.value !== null && d.value !== undefined);
            
            if (formattedData.length > 0) {
              series.setData(formattedData);
              indicatorSeriesRef.current[`${indicatorName}_primary`] = series;
            }
          }

          // Add additional series (other periods)
          if (indicatorData.additional) {
            Object.entries(indicatorData.additional).forEach(([key, values]) => {
              if (key.startsWith(indicatorName)) {
                const series = chart.addLineSeries({
                  color: indicatorName === 'sma' ? '#ff6600' : '#0099cc',
                  lineWidth: 1,
                  lineStyle: 2, // Dashed
                  crosshairMarkerVisible: false,
                });

                const formattedData = values
                  .map((value, index) => ({
                    time: indicatorData.timestamps[index],
                    value: value
                  }))
                  .filter(d => d.value !== null);

                series.setData(formattedData);
                indicatorSeriesRef.current[key] = series;
              }
            });
          }
          break;

        case 'bollinger_bands':
          // Upper band
          if (indicatorData.additional?.upper_band) {
            const upperSeries = chart.addLineSeries({
              color: '#ff00ff',
              lineWidth: 1,
              lineStyle: 2,
              crosshairMarkerVisible: false,
            });

            const upperData = indicatorData.additional.upper_band
              .map((value, index) => ({
                time: indicatorData.timestamps[index],
                value: value
              }))
              .filter(d => d.value !== null);

            upperSeries.setData(upperData);
            indicatorSeriesRef.current['bb_upper'] = upperSeries;
          }

          // Middle band (SMA)
          if (indicatorData.values) {
            const middleSeries = chart.addLineSeries({
              color: '#ff00ff',
              lineWidth: 2,
              crosshairMarkerVisible: false,
            });

            const middleData = indicatorData.values
              .map((value, index) => ({
                time: indicatorData.timestamps[index],
                value: value
              }))
              .filter(d => d.value !== null);

            middleSeries.setData(middleData);
            indicatorSeriesRef.current['bb_middle'] = middleSeries;
          }

          // Lower band
          if (indicatorData.additional?.lower_band) {
            const lowerSeries = chart.addLineSeries({
              color: '#ff00ff',
              lineWidth: 1,
              lineStyle: 2,
              crosshairMarkerVisible: false,
            });

            const lowerData = indicatorData.additional.lower_band
              .map((value, index) => ({
                time: indicatorData.timestamps[index],
                value: value
              }))
              .filter(d => d.value !== null);

            lowerSeries.setData(lowerData);
            indicatorSeriesRef.current['bb_lower'] = lowerSeries;
          }
          break;

        case 'ichimoku':
          // Tenkan-sen (Conversion Line)
          if (indicatorData.values) {
            const tenkanSeries = chart.addLineSeries({
              color: '#ff3366',
              lineWidth: 1,
              crosshairMarkerVisible: false,
            });

            const tenkanData = indicatorData.values
              .map((value, index) => ({
                time: indicatorData.timestamps[index],
                value: value
              }))
              .filter(d => d.value !== null);

            tenkanSeries.setData(tenkanData);
            indicatorSeriesRef.current['ichimoku_tenkan'] = tenkanSeries;
          }

          // Kijun-sen (Base Line)
          if (indicatorData.additional?.kijun_sen) {
            const kijunSeries = chart.addLineSeries({
              color: '#0066ff',
              lineWidth: 1,
              crosshairMarkerVisible: false,
            });

            const kijunData = indicatorData.additional.kijun_sen
              .map((value, index) => ({
                time: indicatorData.timestamps[index],
                value: value
              }))
              .filter(d => d.value !== null);

            kijunSeries.setData(kijunData);
            indicatorSeriesRef.current['ichimoku_kijun'] = kijunSeries;
          }

          // Senkou Span A & B (Cloud)
          // Note: In production, you'd use area series between these lines
          if (indicatorData.additional?.senkou_span_a) {
            const senkouASeries = chart.addLineSeries({
              color: '#00ff88',
              lineWidth: 1,
              lineStyle: 2,
              crosshairMarkerVisible: false,
            });

            const senkouAData = indicatorData.additional.senkou_span_a
              .map((value, index) => ({
                time: indicatorData.timestamps[index],
                value: value
              }))
              .filter(d => d.value !== null);

            senkouASeries.setData(senkouAData);
            indicatorSeriesRef.current['ichimoku_senkou_a'] = senkouASeries;
          }

          if (indicatorData.additional?.senkou_span_b) {
            const senkouBSeries = chart.addLineSeries({
              color: '#ff9900',
              lineWidth: 1,
              lineStyle: 2,
              crosshairMarkerVisible: false,
            });

            const senkouBData = indicatorData.additional.senkou_span_b
              .map((value, index) => ({
                time: indicatorData.timestamps[index],
                value: value
              }))
              .filter(d => d.value !== null);

            senkouBSeries.setData(senkouBData);
            indicatorSeriesRef.current['ichimoku_senkou_b'] = senkouBSeries;
          }
          break;

        default:
          // Handle other indicators as needed
          break;
      }
    });

    return () => {
      // Cleanup on unmount
      const currentChart = chartInstanceRef.current;
      const currentSeries = { ...indicatorSeriesRef.current };
      
      // Clear the ref immediately to prevent double cleanup
      indicatorSeriesRef.current = {};
      chartInstanceRef.current = null;
      
      // Remove all series
      Object.entries(currentSeries).forEach(([key, series]) => {
        try {
          if (series && currentChart && typeof currentChart.removeSeries === 'function') {
            currentChart.removeSeries(series);
          }
        } catch (e) {
          // Silently ignore - chart might be disposed
        }
      });
    };
  }, [chart, indicators, selectedIndicators]);

  // Render indicator values overlay
  const renderIndicatorInfo = () => {
    if (!indicators) return null;

    const currentValues = {};
    
    selectedIndicators.forEach(indicatorName => {
      const indicatorData = indicators[indicatorName];
      if (indicatorData && indicatorData.values && indicatorData.values.length > 0) {
        const lastIndex = indicatorData.values.length - 1;
        currentValues[indicatorName] = {
          value: indicatorData.values[lastIndex],
          metadata: indicatorData.metadata
        };
      }
    });

    if (Object.keys(currentValues).length === 0) return null;

    return (
      <div className="indicator-info">
        {Object.entries(currentValues).map(([name, data]) => (
          <div key={name} className="indicator-info-item">
            <span className="indicator-label">{name.toUpperCase()}:</span>
            <span className="indicator-value">
              {data.value !== null && data.value !== undefined 
                ? typeof data.value === 'number' 
                  ? data.value.toFixed(2) 
                  : data.value
                : 'N/A'}
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="indicators-overlay">
      {renderIndicatorInfo()}
    </div>
  );
};

export default Indicators;