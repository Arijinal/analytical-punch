import React from 'react';
import { useChartStore } from '../../store/chartStore';
import './Controls.css';

const timeframes = [
  { value: '1m', label: '1m' },
  { value: '5m', label: '5m' },
  { value: '15m', label: '15m' },
  { value: '30m', label: '30m' },
  { value: '1h', label: '1H' },
  { value: '4h', label: '4H' },
  { value: '1d', label: '1D' },
  { value: '1w', label: '1W' },
];

const TimeframeSelector = () => {
  const { selectedTimeframe, setTimeframe } = useChartStore();

  return (
    <div className="timeframe-selector">
      {timeframes.map(({ value, label }) => (
        <button
          key={value}
          className={`timeframe-btn ${selectedTimeframe === value ? 'active' : ''}`}
          onClick={() => setTimeframe(value)}
        >
          {label}
        </button>
      ))}
    </div>
  );
};

export default TimeframeSelector;