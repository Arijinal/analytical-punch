import React, { useState, useEffect } from 'react';
import { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useChartStore } from '../../store/chartStore';
import api from '../../services/api';
import toast from 'react-hot-toast';
import './Backtest.css';

const BacktestDashboard = () => {
  const { selectedSymbol } = useChartStore();
  
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState('momentum_punch');
  const [backtestConfig, setBacktestConfig] = useState({
    symbol: selectedSymbol,
    strategy: 'momentum_punch',
    start_date: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
    initial_capital: 10000,
    position_size: 0.1,
    stop_loss: 0.02,
    take_profit: 0.04,
    timeframe: '1h'
  });
  
  const [backtestResults, setBacktestResults] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [comparisonResults, setComparisonResults] = useState(null);

  useEffect(() => {
    fetchStrategies();
  }, []);

  useEffect(() => {
    setBacktestConfig(prev => ({ ...prev, symbol: selectedSymbol }));
  }, [selectedSymbol]);

  const fetchStrategies = async () => {
    try {
      const data = await api.getBacktestStrategies();
      setStrategies(data);
    } catch (error) {
      toast.error('Failed to load strategies');
    }
  };

  const runBacktest = async () => {
    setIsRunning(true);
    try {
      const results = await api.runBacktest(backtestConfig);
      setBacktestResults(results);
      toast.success('Backtest completed successfully');
    } catch (error) {
      toast.error('Backtest failed: ' + error.message);
    } finally {
      setIsRunning(false);
    }
  };

  const runComparison = async () => {
    setIsRunning(true);
    try {
      const results = await api.compareStrategies({
        symbol: selectedSymbol,
        strategies: strategies.map(s => s.name),
        start_date: backtestConfig.start_date,
        end_date: backtestConfig.end_date,
        initial_capital: backtestConfig.initial_capital
      });
      setComparisonResults(results);
      toast.success('Strategy comparison completed');
    } catch (error) {
      toast.error('Comparison failed: ' + error.message);
    } finally {
      setIsRunning(false);
    }
  };

  const handleConfigChange = (field, value) => {
    setBacktestConfig(prev => ({ ...prev, [field]: value }));
  };

  const formatMetric = (value, type = 'number') => {
    if (value === null || value === undefined) return 'N/A';
    
    switch (type) {
      case 'percent':
        return `${value.toFixed(2)}%`;
      case 'money':
        return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      case 'ratio':
        return value.toFixed(2);
      default:
        return value.toFixed(2);
    }
  };

  return (
    <div className="backtest-dashboard">
      <div className="backtest-controls">
        <h3 className="section-title">Backtest Configuration</h3>
        
        <div className="config-grid">
          <div className="config-group">
            <label>Strategy</label>
            <select 
              value={backtestConfig.strategy}
              onChange={(e) => handleConfigChange('strategy', e.target.value)}
              className="config-input"
            >
              {strategies.map(strategy => (
                <option key={strategy.name} value={strategy.name}>
                  {strategy.name.replace('_', ' ').toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          <div className="config-group">
            <label>Timeframe</label>
            <select 
              value={backtestConfig.timeframe}
              onChange={(e) => handleConfigChange('timeframe', e.target.value)}
              className="config-input"
            >
              <option value="15m">15 Minutes</option>
              <option value="30m">30 Minutes</option>
              <option value="1h">1 Hour</option>
              <option value="4h">4 Hours</option>
              <option value="1d">1 Day</option>
            </select>
          </div>

          <div className="config-group">
            <label>Start Date</label>
            <input
              type="date"
              value={backtestConfig.start_date}
              onChange={(e) => handleConfigChange('start_date', e.target.value)}
              className="config-input"
            />
          </div>

          <div className="config-group">
            <label>End Date</label>
            <input
              type="date"
              value={backtestConfig.end_date}
              onChange={(e) => handleConfigChange('end_date', e.target.value)}
              className="config-input"
            />
          </div>

          <div className="config-group">
            <label>Initial Capital</label>
            <input
              type="number"
              value={backtestConfig.initial_capital}
              onChange={(e) => handleConfigChange('initial_capital', parseFloat(e.target.value))}
              className="config-input"
              step="1000"
            />
          </div>

          <div className="config-group">
            <label>Position Size (%)</label>
            <input
              type="number"
              value={backtestConfig.position_size * 100}
              onChange={(e) => handleConfigChange('position_size', parseFloat(e.target.value) / 100)}
              className="config-input"
              step="5"
              min="5"
              max="100"
            />
          </div>

          <div className="config-group">
            <label>Stop Loss (%)</label>
            <input
              type="number"
              value={backtestConfig.stop_loss * 100}
              onChange={(e) => handleConfigChange('stop_loss', parseFloat(e.target.value) / 100)}
              className="config-input"
              step="0.5"
              min="0.5"
              max="10"
            />
          </div>

          <div className="config-group">
            <label>Take Profit (%)</label>
            <input
              type="number"
              value={backtestConfig.take_profit * 100}
              onChange={(e) => handleConfigChange('take_profit', parseFloat(e.target.value) / 100)}
              className="config-input"
              step="0.5"
              min="1"
              max="20"
            />
          </div>
        </div>

        <div className="action-buttons">
          <button 
            className="btn btn-primary" 
            onClick={runBacktest}
            disabled={isRunning}
          >
            {isRunning ? 'Running...' : 'Run Backtest'}
          </button>
          
          <button 
            className="btn btn-secondary" 
            onClick={runComparison}
            disabled={isRunning}
          >
            Compare All Strategies
          </button>
        </div>
      </div>

      {backtestResults && (
        <div className="backtest-results">
          <h3 className="section-title">Backtest Results</h3>
          
          {/* Key Metrics */}
          <div className="metrics-grid">
            <div className="metric-card">
              <span className="metric-label">Total Return</span>
              <span className={`metric-value ${backtestResults.metrics.total_return >= 0 ? 'positive' : 'negative'}`}>
                {formatMetric(backtestResults.metrics.total_return_pct, 'percent')}
              </span>
            </div>
            
            <div className="metric-card">
              <span className="metric-label">Win Rate</span>
              <span className="metric-value">
                {formatMetric(backtestResults.metrics.win_rate * 100, 'percent')}
              </span>
            </div>
            
            <div className="metric-card">
              <span className="metric-label">Sharpe Ratio</span>
              <span className="metric-value">
                {formatMetric(backtestResults.metrics.sharpe_ratio, 'ratio')}
              </span>
            </div>
            
            <div className="metric-card">
              <span className="metric-label">Max Drawdown</span>
              <span className="metric-value negative">
                {formatMetric(backtestResults.metrics.max_drawdown_pct, 'percent')}
              </span>
            </div>
            
            <div className="metric-card">
              <span className="metric-label">Total Trades</span>
              <span className="metric-value">
                {backtestResults.metrics.total_trades}
              </span>
            </div>
            
            <div className="metric-card">
              <span className="metric-label">Profit Factor</span>
              <span className="metric-value">
                {formatMetric(backtestResults.metrics.profit_factor, 'ratio')}
              </span>
            </div>
          </div>

          {/* Equity Curve */}
          <div className="chart-section">
            <h4 className="chart-title">Equity Curve</h4>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={
                backtestResults.equity_curve.timestamps.map((time, index) => ({
                  time: new Date(time).toLocaleDateString(),
                  equity: backtestResults.equity_curve.values[index]
                }))
              }>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="time" stroke="#707070" />
                <YAxis stroke="#707070" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e1e1e', border: '1px solid #2a2a2a' }}
                  labelStyle={{ color: '#a0a0a0' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="equity" 
                  stroke="#00d4ff" 
                  fill="#00d4ff20" 
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Trade Distribution */}
          <div className="chart-section">
            <h4 className="chart-title">Trade Distribution</h4>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={[
                { name: 'Wins', value: backtestResults.metrics.winning_trades, fill: '#00ff88' },
                { name: 'Losses', value: backtestResults.metrics.losing_trades, fill: '#ff3366' }
              ]}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="name" stroke="#707070" />
                <YAxis stroke="#707070" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e1e1e', border: '1px solid #2a2a2a' }}
                />
                <Bar dataKey="value" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {comparisonResults && (
        <div className="comparison-results">
          <h3 className="section-title">Strategy Comparison</h3>
          
          <div className="comparison-table">
            <table>
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Total Return</th>
                  <th>Sharpe Ratio</th>
                  <th>Max Drawdown</th>
                  <th>Win Rate</th>
                  <th>Total Trades</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(comparisonResults.results).map(([strategy, metrics]) => (
                  <tr key={strategy} className={strategy === comparisonResults.best_strategy ? 'best-strategy' : ''}>
                    <td>{strategy.replace('_', ' ').toUpperCase()}</td>
                    <td className={metrics.total_return >= 0 ? 'positive' : 'negative'}>
                      {formatMetric(metrics.total_return * 100, 'percent')}
                    </td>
                    <td>{formatMetric(metrics.sharpe_ratio, 'ratio')}</td>
                    <td className="negative">{formatMetric(metrics.max_drawdown * 100, 'percent')}</td>
                    <td>{formatMetric(metrics.win_rate * 100, 'percent')}</td>
                    <td>{metrics.total_trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default BacktestDashboard;