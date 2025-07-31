import React, { useEffect, useState } from 'react';
import Select from 'react-select';
import { useChartStore } from '../../store/chartStore';
import './Controls.css';

const TickerSelector = () => {
  const { 
    selectedSymbol, 
    setSymbol, 
    availableSymbols, 
    fetchAvailableSymbols 
  } = useChartStore();
  
  const [searchInput, setSearchInput] = useState('');

  useEffect(() => {
    fetchAvailableSymbols();
  }, []);

  // Custom styles for react-select to match dark theme
  const customStyles = {
    control: (provided) => ({
      ...provided,
      backgroundColor: 'var(--bg-tertiary)',
      borderColor: 'var(--border-color)',
      '&:hover': {
        borderColor: 'var(--accent-primary)'
      },
      minWidth: '200px'
    }),
    menu: (provided) => ({
      ...provided,
      backgroundColor: 'var(--bg-secondary)',
      border: '1px solid var(--border-color)',
    }),
    option: (provided, state) => ({
      ...provided,
      backgroundColor: state.isFocused ? 'var(--bg-tertiary)' : 'transparent',
      color: 'var(--text-primary)',
      '&:hover': {
        backgroundColor: 'var(--bg-tertiary)'
      }
    }),
    singleValue: (provided) => ({
      ...provided,
      color: 'var(--text-primary)'
    }),
    input: (provided) => ({
      ...provided,
      color: 'var(--text-primary)'
    }),
    placeholder: (provided) => ({
      ...provided,
      color: 'var(--text-secondary)'
    }),
    dropdownIndicator: (provided) => ({
      ...provided,
      color: 'var(--text-secondary)',
      '&:hover': {
        color: 'var(--text-primary)'
      }
    })
  };

  // Format options with source badge
  const formatOptionLabel = ({ label, source }) => (
    <div className="ticker-option">
      <span className="ticker-symbol">{label}</span>
      <span className={`ticker-source ${source}`}>{source}</span>
    </div>
  );

  // Group options by source
  const groupedOptions = availableSymbols.reduce((acc, symbol) => {
    const group = acc.find(g => g.label === symbol.source);
    if (group) {
      group.options.push(symbol);
    } else {
      acc.push({
        label: symbol.source,
        options: [symbol]
      });
    }
    return acc;
  }, []);

  const handleChange = (option) => {
    if (option) {
      setSymbol(option.value);
    }
  };

  return (
    <div className="ticker-selector">
      <Select
        value={availableSymbols.find(s => s.value === selectedSymbol)}
        onChange={handleChange}
        options={groupedOptions}
        styles={customStyles}
        placeholder="Search symbols..."
        isSearchable
        isClearable={false}
        formatOptionLabel={formatOptionLabel}
        className="ticker-select"
        classNamePrefix="ticker"
        onInputChange={setSearchInput}
        inputValue={searchInput}
      />
      
      {/* Quick access buttons for popular symbols */}
      <div className="quick-symbols">
        {['BTC/USDT', 'ETH/USDT', 'AAPL', 'SPY'].map(symbol => (
          <button
            key={symbol}
            className={`quick-symbol ${selectedSymbol === symbol ? 'active' : ''}`}
            onClick={() => setSymbol(symbol)}
          >
            {symbol}
          </button>
        ))}
      </div>
    </div>
  );
};

export default TickerSelector;