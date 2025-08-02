import React, { useState } from 'react';

const BotCreator = ({ onBotCreate }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    symbols: ['BTC-USD', 'ETH-USD'],
    timeframes: ['1h', '4h'],
    paper_trading: true,
    initial_capital: 10000,
    max_position_size: 0.1,
    max_daily_loss: 0.05,
    max_drawdown: 0.15,
    max_open_positions: 5
  });

  const [customSymbol, setCustomSymbol] = useState('');
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const popularSymbols = [
    'BTC-USD', 'ETH-USD', 'BNB-USD', 'ADA-USD', 'SOL-USD',
    'DOT-USD', 'LINK-USD', 'MATIC-USD', 'AVAX-USD', 'UNI-USD'
  ];

  const availableTimeframes = [
    { value: '5m', label: '5 Minutes' },
    { value: '15m', label: '15 Minutes' },
    { value: '1h', label: '1 Hour' },
    { value: '4h', label: '4 Hours' },
    { value: '1d', label: '1 Day' }
  ];

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : 
              type === 'number' ? parseFloat(value) : value
    }));
    
    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  const handleSymbolToggle = (symbol) => {
    setFormData(prev => ({
      ...prev,
      symbols: prev.symbols.includes(symbol)
        ? prev.symbols.filter(s => s !== symbol)
        : [...prev.symbols, symbol]
    }));
  };

  const handleAddCustomSymbol = () => {
    if (customSymbol.trim() && !formData.symbols.includes(customSymbol.trim().toUpperCase())) {
      setFormData(prev => ({
        ...prev,
        symbols: [...prev.symbols, customSymbol.trim().toUpperCase()]
      }));
      setCustomSymbol('');
    }
  };

  const handleRemoveSymbol = (symbol) => {
    setFormData(prev => ({
      ...prev,
      symbols: prev.symbols.filter(s => s !== symbol)
    }));
  };

  const handleTimeframeToggle = (timeframe) => {
    setFormData(prev => ({
      ...prev,
      timeframes: prev.timeframes.includes(timeframe)
        ? prev.timeframes.filter(t => t !== timeframe)
        : [...prev.timeframes, timeframe]
    }));
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Bot name is required';
    }

    if (formData.symbols.length === 0) {
      newErrors.symbols = 'At least one symbol is required';
    }

    if (formData.timeframes.length === 0) {
      newErrors.timeframes = 'At least one timeframe is required';
    }

    if (formData.initial_capital <= 0) {
      newErrors.initial_capital = 'Initial capital must be greater than 0';
    }

    if (formData.max_position_size <= 0 || formData.max_position_size > 1) {
      newErrors.max_position_size = 'Position size must be between 0 and 1';
    }

    if (formData.max_daily_loss <= 0 || formData.max_daily_loss > 1) {
      newErrors.max_daily_loss = 'Daily loss limit must be between 0 and 1';
    }

    if (formData.max_drawdown <= 0 || formData.max_drawdown > 1) {
      newErrors.max_drawdown = 'Max drawdown must be between 0 and 1';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    try {
      await onBotCreate(formData);
    } catch (error) {
      console.error('Error creating bot:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bot-creator fade-in">
      <div className="creator-header">
        <h2>Create New Trading Bot</h2>
        <p>Configure your multi-strategy trading bot with advanced risk management</p>
      </div>

      <form onSubmit={handleSubmit} className="creator-form">
        {/* Basic Configuration */}
        <div className="form-section">
          <h3>Basic Configuration</h3>
          
          <div className="form-group">
            <label htmlFor="name">Bot Name *</label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              placeholder="e.g., My Trading Bot"
              className={errors.name ? 'error' : ''}
            />
            {errors.name && <span className="error-message">{errors.name}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              placeholder="Optional description of your bot's purpose"
              rows="3"
            />
          </div>

          <div className="form-group">
            <label>Trading Mode</label>
            <div className="radio-group">
              <label className="radio-label">
                <input
                  type="radio"
                  name="paper_trading"
                  checked={formData.paper_trading}
                  onChange={() => setFormData(prev => ({ ...prev, paper_trading: true }))}
                />
                <span className="radio-custom"></span>
                📝 Paper Trading (Recommended)
              </label>
              <label className="radio-label">
                <input
                  type="radio"
                  name="paper_trading"
                  checked={!formData.paper_trading}
                  onChange={() => setFormData(prev => ({ ...prev, paper_trading: false }))}
                />
                <span className="radio-custom"></span>
                💰 Live Trading (Real money)
              </label>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="initial_capital">Initial Capital ($) *</label>
            <input
              type="number"
              id="initial_capital"
              name="initial_capital"
              value={formData.initial_capital}
              onChange={handleInputChange}
              min="100"
              step="100"
              className={errors.initial_capital ? 'error' : ''}
            />
            {errors.initial_capital && <span className="error-message">{errors.initial_capital}</span>}
          </div>
        </div>

        {/* Trading Symbols */}
        <div className="form-section">
          <h3>Trading Symbols</h3>
          
          <div className="symbols-section">
            <div className="popular-symbols">
              <h4>Popular Symbols</h4>
              <div className="symbol-grid">
                {popularSymbols.map(symbol => (
                  <button
                    key={symbol}
                    type="button"
                    className={`symbol-btn ${formData.symbols.includes(symbol) ? 'selected' : ''}`}
                    onClick={() => handleSymbolToggle(symbol)}
                  >
                    {symbol}
                  </button>
                ))}
              </div>
            </div>

            <div className="custom-symbol">
              <h4>Add Custom Symbol</h4>
              <div className="custom-symbol-input">
                <input
                  type="text"
                  value={customSymbol}
                  onChange={(e) => setCustomSymbol(e.target.value)}
                  placeholder="e.g., DOT-USD"
                  onKeyPress={(e) => e.key === 'Enter' && handleAddCustomSymbol()}
                />
                <button type="button" onClick={handleAddCustomSymbol}>
                  Add
                </button>
              </div>
            </div>

            <div className="selected-symbols">
              <h4>Selected Symbols ({formData.symbols.length})</h4>
              <div className="selected-symbols-list">
                {formData.symbols.map(symbol => (
                  <span key={symbol} className="selected-symbol">
                    {symbol}
                    <button
                      type="button"
                      onClick={() => handleRemoveSymbol(symbol)}
                      className="remove-symbol"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              {errors.symbols && <span className="error-message">{errors.symbols}</span>}
            </div>
          </div>
        </div>

        {/* Timeframes */}
        <div className="form-section">
          <h3>Timeframes</h3>
          <div className="timeframe-grid">
            {availableTimeframes.map(({ value, label }) => (
              <label key={value} className="checkbox-label">
                <input
                  type="checkbox"
                  checked={formData.timeframes.includes(value)}
                  onChange={() => handleTimeframeToggle(value)}
                />
                <span className="checkbox-custom"></span>
                {label}
              </label>
            ))}
          </div>
          {errors.timeframes && <span className="error-message">{errors.timeframes}</span>}
        </div>

        {/* Risk Management */}
        <div className="form-section">
          <h3>Risk Management</h3>
          
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="max_position_size">Max Position Size (%)</label>
              <input
                type="number"
                id="max_position_size"
                name="max_position_size"
                value={formData.max_position_size * 100}
                onChange={(e) => setFormData(prev => ({ 
                  ...prev, 
                  max_position_size: parseFloat(e.target.value) / 100 
                }))}
                min="1"
                max="100"
                step="1"
                className={errors.max_position_size ? 'error' : ''}
              />
              <small>Maximum percentage of portfolio per position</small>
              {errors.max_position_size && <span className="error-message">{errors.max_position_size}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="max_daily_loss">Max Daily Loss (%)</label>
              <input
                type="number"
                id="max_daily_loss"
                name="max_daily_loss"
                value={formData.max_daily_loss * 100}
                onChange={(e) => setFormData(prev => ({ 
                  ...prev, 
                  max_daily_loss: parseFloat(e.target.value) / 100 
                }))}
                min="1"
                max="50"
                step="1"
                className={errors.max_daily_loss ? 'error' : ''}
              />
              <small>Maximum daily loss before bot pauses</small>
              {errors.max_daily_loss && <span className="error-message">{errors.max_daily_loss}</span>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="max_drawdown">Max Drawdown (%)</label>
              <input
                type="number"
                id="max_drawdown"
                name="max_drawdown"
                value={formData.max_drawdown * 100}
                onChange={(e) => setFormData(prev => ({ 
                  ...prev, 
                  max_drawdown: parseFloat(e.target.value) / 100 
                }))}
                min="5"
                max="50"
                step="1"
                className={errors.max_drawdown ? 'error' : ''}
              />
              <small>Maximum drawdown before bot stops</small>
              {errors.max_drawdown && <span className="error-message">{errors.max_drawdown}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="max_open_positions">Max Open Positions</label>
              <input
                type="number"
                id="max_open_positions"
                name="max_open_positions"
                value={formData.max_open_positions}
                onChange={handleInputChange}
                min="1"
                max="20"
                step="1"
              />
              <small>Maximum number of concurrent positions</small>
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="form-actions">
          <button
            type="submit"
            className="create-btn"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Creating Bot...' : 'Create Trading Bot'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default BotCreator;