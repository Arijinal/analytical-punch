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
          className="bot-action-btn primary"
          onClick={(e) => {
            e.stopPropagation();
            onBotAction(bot.bot_id, 'start');
          }}
        >
          ▶️ Start
        </button>
      );
    }

    if (bot.status === 'running') {
      actions.push(
        <button
          key="pause"
          className="bot-action-btn secondary"
          onClick={(e) => {
            e.stopPropagation();
            onBotAction(bot.bot_id, 'pause');
          }}
        >
          ⏸️ Pause
        </button>
      );
      actions.push(
        <button
          key="stop"
          className="bot-action-btn danger"
          onClick={(e) => {
            e.stopPropagation();
            onBotAction(bot.bot_id, 'stop');
          }}
        >
          ⏹️ Stop
        </button>
      );
    }

    if (bot.status === 'paused') {
      actions.push(
        <button
          key="resume"
          className="bot-action-btn primary"
          onClick={(e) => {
            e.stopPropagation();
            onBotAction(bot.bot_id, 'resume');
          }}
        >
          ▶️ Resume
        </button>
      );
      actions.push(
        <button
          key="stop"
          className="bot-action-btn danger"
          onClick={(e) => {
            e.stopPropagation();
            onBotAction(bot.bot_id, 'stop');
          }}
        >
          ⏹️ Stop
        </button>
      );
    }

    return actions;
  };

  if (bots.length === 0) {
    return (
      <div className="bot-list">
        <div className="bot-list-header">
          <h2>Trading Bots</h2>
        </div>
        <div className="empty-state">
          <span className="empty-icon">🤖</span>
          <h3>No Trading Bots</h3>
          <p>Create your first trading bot to get started</p>
          <button 
            className="create-first-bot-btn"
            onClick={() => document.querySelector('.nav-tab:nth-child(2)')?.click()}
          >
            Create Your First Bot
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bot-list fade-in">
      <div className="bot-list-header">
        <h2>Trading Bots ({bots.length})</h2>
        <div className="list-view-toggle">
          <button className="view-btn active">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <rect x="1" y="1" width="6" height="6" rx="1"/>
              <rect x="9" y="1" width="6" height="6" rx="1"/>
              <rect x="1" y="9" width="6" height="6" rx="1"/>
              <rect x="9" y="9" width="6" height="6" rx="1"/>
            </svg>
            Grid
          </button>
          <button className="view-btn">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <rect x="1" y="2" width="14" height="2" rx="1"/>
              <rect x="1" y="7" width="14" height="2" rx="1"/>
              <rect x="1" y="12" width="14" height="2" rx="1"/>
            </svg>
            List
          </button>
        </div>
      </div>

      <div className="bot-grid">
        {bots.map((bot) => (
          <div
            key={bot.bot_id}
            className={`bot-card ${bot.status}`}
            onClick={() => onBotSelect(bot)}
          >
            <div className="bot-card-header">
              <div className="bot-info">
                <h3>{bot.name}</h3>
                <p>{bot.description || 'Multi-strategy trading bot'}</p>
              </div>
              <div className={`bot-status ${bot.status}`}>
                <span className="status-indicator"></span>
                {bot.status}
              </div>
            </div>

            <div className="bot-symbols">
              <small>Trading: {bot.symbols?.join(', ') || 'N/A'} | {bot.paper_trading ? '📝 Paper' : '💰 Live'}</small>
            </div>

            <div className="bot-metrics">
              <div className="metric">
                <span className="metric-label">Capital</span>
                <span className="metric-value">
                  {formatCurrency(bot.live_status?.portfolio_value || bot.current_capital || 0)}
                </span>
              </div>

              <div className="metric">
                <span className="metric-label">Return</span>
                <span className={`metric-value ${bot.total_return_pct >= 0 ? 'positive' : 'negative'}`}>
                  {formatPercentage(bot.total_return_pct || 0)}
                </span>
              </div>

              <div className="metric">
                <span className="metric-label">Win Rate</span>
                <span className="metric-value">
                  {bot.win_rate ? `${(bot.win_rate * 100).toFixed(1)}%` : '0%'}
                </span>
              </div>

              <div className="metric">
                <span className="metric-label">Trades</span>
                <span className="metric-value">{bot.total_trades || 0}</span>
              </div>
            </div>


            <div className="bot-actions" onClick={(e) => e.stopPropagation()}>
              {renderBotActions(bot)}
              <button
                className="bot-action-btn secondary"
                onClick={(e) => {
                  e.stopPropagation();
                  onBotSelect(bot);
                }}
              >
                📊 Details
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default BotList;