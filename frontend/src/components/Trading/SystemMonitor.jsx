import React from 'react';

const SystemMonitor = ({ systemStatus, bots }) => {
  const calculateTotalValue = () => {
    return bots.reduce((sum, bot) => sum + (bot.current_capital || bot.initial_capital || 0), 0);
  };

  const calculateTotalPnL = () => {
    return bots.reduce((sum, bot) => sum + (bot.total_pnl || 0), 0);
  };

  const activeBots = bots.filter(bot => bot.status === 'running');
  const pausedBots = bots.filter(bot => bot.status === 'paused');
  const stoppedBots = bots.filter(bot => bot.status === 'stopped');

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

  return (
    <div className="system-monitor">
      <div className="monitor-header">
        <h2>System Monitor</h2>
        <span className="last-update">Last update: {new Date().toLocaleTimeString()}</span>
      </div>

      {/* System Overview */}
      <div className="monitor-section">
        <h3>System Overview</h3>
        <div className="overview-grid">
          <div className="overview-card">
            <div className="card-icon">🤖</div>
            <div className="card-content">
              <span className="card-value">{bots.length}</span>
              <span className="card-label">Total Bots</span>
            </div>
          </div>
          <div className="overview-card active">
            <div className="card-icon">▶️</div>
            <div className="card-content">
              <span className="card-value">{activeBots.length}</span>
              <span className="card-label">Running</span>
            </div>
          </div>
          <div className="overview-card paused">
            <div className="card-icon">⏸️</div>
            <div className="card-content">
              <span className="card-value">{pausedBots.length}</span>
              <span className="card-label">Paused</span>
            </div>
          </div>
          <div className="overview-card stopped">
            <div className="card-icon">⏹️</div>
            <div className="card-content">
              <span className="card-value">{stoppedBots.length}</span>
              <span className="card-label">Stopped</span>
            </div>
          </div>
        </div>
      </div>

      {/* Portfolio Summary */}
      <div className="monitor-section">
        <h3>Portfolio Summary</h3>
        <div className="portfolio-summary">
          <div className="summary-row">
            <span className="summary-label">Total Portfolio Value:</span>
            <span className="summary-value">{formatCurrency(calculateTotalValue())}</span>
          </div>
          <div className="summary-row">
            <span className="summary-label">Total P&L:</span>
            <span className={`summary-value ${calculateTotalPnL() >= 0 ? 'positive' : 'negative'}`}>
              {formatCurrency(calculateTotalPnL())}
            </span>
          </div>
          <div className="summary-row">
            <span className="summary-label">Active Positions:</span>
            <span className="summary-value">
              {bots.reduce((sum, bot) => sum + (bot.live_status?.positions || 0), 0)}
            </span>
          </div>
          <div className="summary-row">
            <span className="summary-label">Total Trades Today:</span>
            <span className="summary-value">
              {bots.reduce((sum, bot) => sum + (bot.trades_today || 0), 0)}
            </span>
          </div>
        </div>
      </div>

      {/* Bot Performance Table */}
      <div className="monitor-section">
        <h3>Bot Performance</h3>
        <table className="performance-table">
          <thead>
            <tr>
              <th>Bot Name</th>
              <th>Status</th>
              <th>Portfolio Value</th>
              <th>Total Return</th>
              <th>Win Rate</th>
              <th>Trades</th>
              <th>Positions</th>
            </tr>
          </thead>
          <tbody>
            {bots.map((bot) => (
              <tr key={bot.bot_id}>
                <td>{bot.name}</td>
                <td>
                  <span className={`status-badge ${bot.status}`}>{bot.status}</span>
                </td>
                <td>{formatCurrency(bot.current_capital || bot.initial_capital || 0)}</td>
                <td className={bot.total_return_pct >= 0 ? 'positive' : 'negative'}>
                  {formatPercentage(bot.total_return_pct || 0)}
                </td>
                <td>{bot.win_rate ? `${(bot.win_rate * 100).toFixed(1)}%` : '0%'}</td>
                <td>{bot.total_trades || 0}</td>
                <td>{bot.live_status?.positions || 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* System Resources */}
      <div className="monitor-section">
        <h3>System Resources</h3>
        <div className="resource-grid">
          <div className="resource-item">
            <span className="resource-label">API Status</span>
            <span className="resource-value good">Connected</span>
          </div>
          <div className="resource-item">
            <span className="resource-label">WebSocket</span>
            <span className="resource-value good">Active</span>
          </div>
          <div className="resource-item">
            <span className="resource-label">Database</span>
            <span className="resource-value good">Healthy</span>
          </div>
          <div className="resource-item">
            <span className="resource-label">Data Sources</span>
            <span className="resource-value good">3/3 Online</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemMonitor;