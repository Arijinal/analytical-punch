import React, { useState, useEffect } from 'react';
import api from '../../services/api';
import toast from 'react-hot-toast';

const BotDetails = ({ bot, onBotAction }) => {
  const [performance, setPerformance] = useState(null);
  const [positions, setPositions] = useState([]);
  const [recentTrades, setRecentTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (bot) {
      loadBotDetails();
    }
  }, [bot?.bot_id]);

  const loadBotDetails = async () => {
    if (!bot?.bot_id) return;
    
    setLoading(true);
    try {
      // Load performance data
      const perfResponse = await fetch(`/api/v1/trading/bots/${bot.bot_id}/performance`);
      const perfData = await perfResponse.json();
      setPerformance(perfData);

      // Load positions
      const posResponse = await fetch(`/api/v1/trading/bots/${bot.bot_id}/positions`);
      const posData = await posResponse.json();
      setPositions(posData);

      // Load recent trades
      const tradesResponse = await fetch(`/api/v1/trading/bots/${bot.bot_id}/trades?limit=10`);
      const tradesData = await tradesResponse.json();
      setRecentTrades(tradesData);
    } catch (error) {
      console.error('Error loading bot details:', error);
      toast.error('Failed to load bot details');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatPercentage = (value) => {
    return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`;
  };

  const getActionButtons = () => {
    const buttons = [];

    if (bot.status === 'stopped') {
      buttons.push(
        <button
          key="start"
          className="action-btn start"
          onClick={() => onBotAction(bot.bot_id, 'start')}
        >
          Start Bot
        </button>
      );
    } else if (bot.status === 'running') {
      buttons.push(
        <button
          key="pause"
          className="action-btn pause"
          onClick={() => onBotAction(bot.bot_id, 'pause')}
        >
          Pause
        </button>,
        <button
          key="stop"
          className="action-btn stop"
          onClick={() => onBotAction(bot.bot_id, 'stop')}
        >
          Stop
        </button>
      );
    } else if (bot.status === 'paused') {
      buttons.push(
        <button
          key="resume"
          className="action-btn start"
          onClick={() => onBotAction(bot.bot_id, 'resume')}
        >
          Resume
        </button>,
        <button
          key="stop"
          className="action-btn stop"
          onClick={() => onBotAction(bot.bot_id, 'stop')}
        >
          Stop
        </button>
      );
    }

    return buttons;
  };

  if (loading) {
    return <div className="bot-details loading">Loading bot details...</div>;
  }

  if (!bot) {
    return <div className="bot-details">No bot selected</div>;
  }

  return (
    <div className="bot-details">
      <div className="details-header">
        <div className="header-info">
          <h2>{bot.name}</h2>
          <span className={`status-badge ${bot.status}`}>{bot.status}</span>
        </div>
        <div className="header-actions">
          {getActionButtons()}
        </div>
      </div>

      {/* Performance Overview */}
      <div className="details-section">
        <h3>Performance Overview</h3>
        <div className="metrics-grid">
          <div className="metric-card">
            <span className="metric-label">Portfolio Value</span>
            <span className="metric-value">{formatCurrency(bot.current_capital || 0)}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Total Return</span>
            <span className={`metric-value ${bot.total_return_pct >= 0 ? 'positive' : 'negative'}`}>
              {formatPercentage(bot.total_return_pct || 0)}
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Win Rate</span>
            <span className="metric-value">{(bot.win_rate * 100).toFixed(1)}%</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Sharpe Ratio</span>
            <span className="metric-value">{bot.sharpe_ratio?.toFixed(2) || '0.00'}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Max Drawdown</span>
            <span className="metric-value negative">{formatPercentage(bot.max_drawdown || 0)}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Total Trades</span>
            <span className="metric-value">{bot.total_trades || 0}</span>
          </div>
        </div>
      </div>

      {/* Open Positions */}
      <div className="details-section">
        <h3>Open Positions ({positions.length})</h3>
        {positions.length > 0 ? (
          <table className="positions-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Size</th>
                <th>Entry Price</th>
                <th>Current Price</th>
                <th>P&L</th>
                <th>P&L %</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => (
                <tr key={pos.id}>
                  <td>{pos.symbol}</td>
                  <td className={pos.side}>{pos.side}</td>
                  <td>{pos.size}</td>
                  <td>{formatCurrency(pos.entry_price)}</td>
                  <td>{formatCurrency(pos.current_price)}</td>
                  <td className={pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}>
                    {formatCurrency(pos.unrealized_pnl)}
                  </td>
                  <td className={pos.pnl_percentage >= 0 ? 'positive' : 'negative'}>
                    {formatPercentage(pos.pnl_percentage / 100)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">No open positions</div>
        )}
      </div>

      {/* Recent Trades */}
      <div className="details-section">
        <h3>Recent Trades</h3>
        {recentTrades.length > 0 ? (
          <table className="trades-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Size</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>P&L</th>
                <th>Strategy</th>
              </tr>
            </thead>
            <tbody>
              {recentTrades.map((trade) => (
                <tr key={trade.id}>
                  <td>{new Date(trade.exit_time).toLocaleString()}</td>
                  <td>{trade.symbol}</td>
                  <td className={trade.side}>{trade.side}</td>
                  <td>{trade.amount}</td>
                  <td>{formatCurrency(trade.entry_price)}</td>
                  <td>{formatCurrency(trade.exit_price)}</td>
                  <td className={trade.pnl >= 0 ? 'positive' : 'negative'}>
                    {formatCurrency(trade.pnl)}
                  </td>
                  <td>{trade.strategy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">No trades yet</div>
        )}
      </div>

      {/* Bot Configuration */}
      <div className="details-section">
        <h3>Configuration</h3>
        <div className="config-grid">
          <div className="config-item">
            <span className="config-label">Symbols:</span>
            <span className="config-value">{bot.symbols?.join(', ')}</span>
          </div>
          <div className="config-item">
            <span className="config-label">Timeframes:</span>
            <span className="config-value">{bot.timeframes?.join(', ')}</span>
          </div>
          <div className="config-item">
            <span className="config-label">Max Position Size:</span>
            <span className="config-value">{(bot.max_position_size * 100).toFixed(0)}%</span>
          </div>
          <div className="config-item">
            <span className="config-label">Max Daily Loss:</span>
            <span className="config-value">{(bot.max_daily_loss * 100).toFixed(0)}%</span>
          </div>
          <div className="config-item">
            <span className="config-label">Max Drawdown:</span>
            <span className="config-value">{(bot.max_drawdown_limit * 100).toFixed(0)}%</span>
          </div>
          <div className="config-item">
            <span className="config-label">Trading Mode:</span>
            <span className="config-value">{bot.paper_trading ? 'Paper Trading' : 'Live Trading'}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BotDetails;