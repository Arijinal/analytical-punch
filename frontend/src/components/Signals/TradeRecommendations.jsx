import React from 'react';
import { useChartStore } from '../../store/chartStore';
import { format } from 'date-fns';
import './Signals.css';

const TradeRecommendations = ({ limit = null }) => {
  const { signals, selectedSymbol } = useChartStore();
  
  // Filter and limit signals
  const displaySignals = limit ? signals.slice(0, limit) : signals;

  if (!displaySignals || displaySignals.length === 0) {
    return (
      <div className="trade-recommendations">
        <h3 className="panel-title">Trade Recommendations</h3>
        <div className="no-signals">
          <p>No trading signals available for {selectedSymbol}</p>
          <span className="hint">Signals will appear when market conditions meet strategy criteria</span>
        </div>
      </div>
    );
  }

  const formatPrice = (price) => {
    return price > 100 ? price.toFixed(2) : price.toFixed(4);
  };

  const getStrategyIcon = (strategy) => {
    const icons = {
      'momentum_punch': '🚀',
      'value_punch': '💎',
      'breakout_punch': '⚡',
      'trend_punch': '📈'
    };
    return icons[strategy] || '📊';
  };

  const getDirectionClass = (direction) => {
    return direction === 'buy' ? 'bullish' : 'bearish';
  };

  return (
    <div className="trade-recommendations">
      <div className="recommendations-header">
        <h3 className="panel-title">Trade Recommendations</h3>
        {limit && signals.length > limit && (
          <span className="view-all">+{signals.length - limit} more</span>
        )}
      </div>

      <div className="signals-list">
        {displaySignals.map((signal, index) => (
          <div key={index} className="signal-card">
            <div className="signal-header">
              <div className="signal-meta">
                <span className="strategy-icon">{getStrategyIcon(signal.strategy)}</span>
                <div>
                  <h4 className="strategy-name">
                    {signal.strategy.replace('_', ' ').toUpperCase()}
                  </h4>
                  <span className="signal-time">
                    {signal.timestamp ? format(new Date(signal.timestamp), 'HH:mm:ss') : 'Just now'}
                  </span>
                </div>
              </div>
              
              <div className={`signal-direction ${getDirectionClass(signal.direction)}`}>
                {signal.direction.toUpperCase()}
              </div>
            </div>

            <div className="signal-details">
              <div className="detail-row">
                <span className="detail-label">Entry Price</span>
                <span className="detail-value">${formatPrice(signal.entry_price)}</span>
              </div>
              
              <div className="detail-row">
                <span className="detail-label">Stop Loss</span>
                <span className="detail-value negative">${formatPrice(signal.stop_loss)}</span>
              </div>
              
              <div className="detail-row">
                <span className="detail-label">Take Profit</span>
                <span className="detail-value positive">
                  ${formatPrice(signal.take_profit_levels[0])}
                  {signal.take_profit_levels.length > 1 && 
                    ` (+${signal.take_profit_levels.length - 1})`
                  }
                </span>
              </div>
              
              <div className="detail-row">
                <span className="detail-label">Risk/Reward</span>
                <span className="detail-value">{signal.risk_reward_ratio.toFixed(2)}:1</span>
              </div>
            </div>

            <div className="signal-metrics">
              <div className="metric">
                <div className="confidence-meter">
                  <span className="metric-label">Confidence</span>
                  <div className="confidence-bar">
                    <div 
                      className="confidence-fill"
                      style={{ width: `${signal.confidence * 100}%` }}
                    />
                  </div>
                  <span className="metric-value">{(signal.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
              
              <div className="metric">
                <span className="metric-label">Strength</span>
                <span className="metric-value">{signal.strength.toFixed(0)}/100</span>
              </div>
            </div>

            <div className="signal-reasoning">
              <p>{signal.reasoning}</p>
            </div>

            <div className="signal-indicators">
              <span className="indicators-label">Based on:</span>
              <div className="indicator-tags">
                {signal.indicators_used.map((indicator, idx) => (
                  <span key={idx} className="indicator-tag">
                    {indicator.toUpperCase()}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TradeRecommendations;