import React from 'react';
import { useChartStore } from '../../store/chartStore';
import './MarketInfo.css';

const MarketInfoPanel = ({ detailed = false }) => {
  const { marketInfo, selectedSymbol } = useChartStore();

  if (!marketInfo) {
    return (
      <div className="market-info-panel">
        <h3 className="panel-title">Market Information</h3>
        <div className="loading-state">Loading market data...</div>
      </div>
    );
  }

  const {
    current_price,
    price_changes,
    volume_analysis,
    volatility,
    key_levels,
    technical_summary,
    market_structure
  } = marketInfo;

  const formatPrice = (price) => {
    if (!price) return 'N/A';
    return price > 100 ? price.toFixed(2) : price.toFixed(4);
  };

  const formatPercent = (value) => {
    if (!value) return '0.00%';
    const formatted = value.toFixed(2);
    return value >= 0 ? `+${formatted}%` : `${formatted}%`;
  };

  return (
    <div className="market-info-panel">
      <h3 className="panel-title">Market Information</h3>
      
      {/* Price Overview */}
      <div className="info-section">
        <h4 className="section-title">Price Overview</h4>
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">Current Price</span>
            <span className="info-value primary">${formatPrice(current_price)}</span>
          </div>
          
          <div className="info-item">
            <span className="info-label">24h Change</span>
            <span className={`info-value ${price_changes?.change_24h_pct >= 0 ? 'positive' : 'negative'}`}>
              {formatPercent(price_changes?.change_24h_pct)}
            </span>
          </div>
          
          <div className="info-item">
            <span className="info-label">7d Change</span>
            <span className={`info-value ${price_changes?.change_7d_pct >= 0 ? 'positive' : 'negative'}`}>
              {formatPercent(price_changes?.change_7d_pct)}
            </span>
          </div>
          
          <div className="info-item">
            <span className="info-label">24h Volume</span>
            <span className="info-value">{volume_analysis?.['24h_volume']?.toLocaleString() || 'N/A'}</span>
          </div>
        </div>
      </div>

      {/* Technical Summary */}
      <div className="info-section">
        <h4 className="section-title">Technical Summary</h4>
        <div className="summary-box">
          <div className="trend-indicator">
            <span className="trend-label">Trend:</span>
            <span className={`trend-value ${technical_summary?.trend}`}>
              {technical_summary?.trend?.toUpperCase() || 'NEUTRAL'}
            </span>
          </div>
          
          <div className="strength-meter">
            <span className="strength-label">Strength:</span>
            <div className="strength-bar">
              <div 
                className="strength-fill"
                style={{ width: `${technical_summary?.strength || 50}%` }}
              />
            </div>
            <span className="strength-value">{technical_summary?.strength || 50}%</span>
          </div>
          
          <p className="recommendation">{technical_summary?.recommendation}</p>
        </div>
      </div>

      {/* Key Levels */}
      <div className="info-section">
        <h4 className="section-title">Key Levels</h4>
        <div className="levels-grid">
          {key_levels?.pivot_points && (
            <>
              <div className="level-item resistance">
                <span className="level-label">R2</span>
                <span className="level-value">${formatPrice(key_levels.pivot_points.r2)}</span>
              </div>
              <div className="level-item resistance">
                <span className="level-label">R1</span>
                <span className="level-value">${formatPrice(key_levels.pivot_points.r1)}</span>
              </div>
              <div className="level-item pivot">
                <span className="level-label">Pivot</span>
                <span className="level-value">${formatPrice(key_levels.pivot_points.pivot)}</span>
              </div>
              <div className="level-item support">
                <span className="level-label">S1</span>
                <span className="level-value">${formatPrice(key_levels.pivot_points.s1)}</span>
              </div>
              <div className="level-item support">
                <span className="level-label">S2</span>
                <span className="level-value">${formatPrice(key_levels.pivot_points.s2)}</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Volatility & Volume */}
      <div className="info-section">
        <h4 className="section-title">Market Dynamics</h4>
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">Volatility</span>
            <span className={`info-value ${volatility?.volatility_regime}`}>
              {volatility?.volatility_regime?.toUpperCase() || 'NORMAL'}
            </span>
          </div>
          
          <div className="info-item">
            <span className="info-label">Volume Trend</span>
            <span className={`info-value ${volume_analysis?.volume_trend}`}>
              {volume_analysis?.volume_trend?.toUpperCase() || 'STABLE'}
            </span>
          </div>
          
          {volume_analysis?.volume_spike && (
            <div className="info-item full-width">
              <span className="alert-badge">Volume Spike Detected!</span>
            </div>
          )}
        </div>
      </div>

      {/* Market Structure - Only in detailed view */}
      {detailed && market_structure && (
        <div className="info-section">
          <h4 className="section-title">Market Structure</h4>
          <div className="structure-info">
            <div className="structure-type">
              <span className={`structure-badge ${market_structure.type}`}>
                {market_structure.type?.toUpperCase()}
              </span>
              <span className="structure-strength">{market_structure.strength}% strength</span>
            </div>
            
            <ul className="characteristics">
              {market_structure.characteristics?.map((char, index) => (
                <li key={index}>{char}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default MarketInfoPanel;