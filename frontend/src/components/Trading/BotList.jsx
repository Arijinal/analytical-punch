import React from 'react';

const BotList = ({ bots, onBotSelect, onBotAction }) => {
  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatPercentage = (value) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'running': return '#51cf66';
      case 'paused': return '#ffd43b';
      case 'stopped': return '#ff8787';
      case 'error': return '#ff6b6b';
      default: return '#868e96';
    }
  };

  const renderBotActions = (bot) => {
    const actions = [];

    if (bot.status === 'stopped') {
      actions.push(
        <button
          key="start"
          className="action-btn start"
          onClick={(e) => {
            e.stopPropagation();
            onBotAction(bot.bot_id, 'start');
          }}
        >
          Start
        </button>
      );
    }

    if (bot.status === 'running') {
      actions.push(
        <button
          key="pause"
          className="action-btn pause"
          onClick={(e) => {
            e.stopPropagation();
            onBotAction(bot.bot_id, 'pause');
          }}
        >
          Pause
        </button>
      );
      actions.push(
        <button
          key="stop"
          className="action-btn stop"
          onClick={(e) => {
            e.stopPropagation();
            onBotAction(bot.bot_id, 'stop');
          }}
        >
          Stop
        </button>
      );
    }

    if (bot.status === 'paused') {
      actions.push(
        <button
          key="resume"
          className="action-btn start"
          onClick={(e) => {
            e.stopPropagation();
            onBotAction(bot.bot_id, 'resume');
          }}
        >
          Resume
        </button>
      );
      actions.push(
        <button
          key="stop"
          className="action-btn stop"
          onClick={(e) => {
            e.stopPropagation();
            onBotAction(bot.bot_id, 'stop');
          }}
        >
          Stop
        </button>
      );
    }

    return actions;
  };

  if (bots.length === 0) {
    return (
      <div className="bot-list">
        <h2>Trading Bots</h2>
        <div className="empty-state">
          <div className="empty-icon">🤖</div>
          <h3>No Trading Bots</h3>
          <p>Create your first trading bot to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bot-list fade-in">
      <div className="list-header">
        <h2>Trading Bots ({bots.length})</h2>
        <div className="list-filters">
          <select className="filter-select">
            <option value="all">All Bots</option>
            <option value="running">Running</option>
            <option value="paused">Paused</option>
            <option value="stopped">Stopped</option>
          </select>
        </div>
      </div>

      <div className="bot-grid">
        {bots.map((bot) => (
          <div
            key={bot.bot_id}
            className={`bot-card ${bot.status}`}
            onClick={() => onBotSelect(bot)}
          >
            <div className="bot-header">
              <h3 className="bot-name">{bot.name}</h3>
              <span 
                className={`bot-status ${bot.status}`}
                style={{ backgroundColor: getStatusColor(bot.status) }}
              >
                {bot.status}
              </span>
            </div>

            <div className="bot-info">
              <div className="bot-description">
                {bot.description || 'Multi-strategy trading bot'}
              </div>
              <div className="bot-symbols">
                <strong>Symbols:</strong> {bot.symbols?.join(', ') || 'N/A'}
              </div>
              <div className="bot-mode">
                {bot.paper_trading ? '📝 Paper Trading' : '💰 Live Trading'}
              </div>
            </div>

            <div className="bot-metrics">
              <div className="metric">
                <span className="metric-label">Portfolio Value</span>
                <span className="metric-value">
                  {formatCurrency(bot.live_status?.portfolio_value || bot.current_capital || 0)}
                </span>
              </div>

              <div className="metric">
                <span className="metric-label">Total Return</span>
                <span className={`metric-value ${bot.total_return_pct >= 0 ? 'positive' : 'negative'}`}>
                  {formatPercentage(bot.total_return_pct || 0)}
                </span>
              </div>

              <div className="metric">
                <span className="metric-label">Total Trades</span>
                <span className="metric-value">{bot.total_trades || 0}</span>
              </div>

              <div className="metric">
                <span className="metric-label">Win Rate</span>
                <span className="metric-value">
                  {bot.win_rate ? `${(bot.win_rate * 100).toFixed(1)}%` : '0%'}
                </span>
              </div>

              <div className="metric">
                <span className="metric-label">Max Drawdown</span>
                <span className="metric-value negative">
                  {bot.max_drawdown ? `${(bot.max_drawdown * 100).toFixed(1)}%` : '0%'}
                </span>
              </div>

              <div className="metric">
                <span className="metric-label">Open Positions</span>
                <span className="metric-value">
                  {bot.live_status?.positions || 0}
                </span>
              </div>
            </div>

            <div className="bot-timing">
              <div className="timing-item">
                <span className="timing-label">Created:</span>
                <span className="timing-value">
                  {new Date(bot.created_at).toLocaleDateString()}
                </span>
              </div>
              {bot.started_at && (
                <div className="timing-item">
                  <span className="timing-label">Started:</span>
                  <span className="timing-value">
                    {new Date(bot.started_at).toLocaleString()}
                  </span>
                </div>
              )}
            </div>

            <div className="bot-actions" onClick={(e) => e.stopPropagation()}>
              {renderBotActions(bot)}
              <button
                className="action-btn details"
                onClick={(e) => {
                  e.stopPropagation();
                  onBotSelect(bot);
                }}
              >
                Details
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default BotList;