import React, { useState, useEffect } from 'react';
import { Toaster } from 'react-hot-toast';
import ChartContainer from './components/Chart/ChartContainer';
import MarketInfoPanel from './components/MarketInfo/MarketInfoPanel';
import TradeRecommendations from './components/Signals/TradeRecommendations';
import TickerSelector from './components/Controls/TickerSelector';
import TimeframeSelector from './components/Controls/TimeframeSelector';
import BacktestDashboard from './components/Backtest/BacktestDashboard';
import TradingDashboard from './components/Trading/TradingDashboard';
import useWebSocket from './hooks/useWebSocket';
import { useChartStore } from './store/chartStore';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('chart');
  const [showBacktest, setShowBacktest] = useState(false);
  
  const { 
    selectedSymbol, 
    selectedTimeframe,
    isLoading,
    error
  } = useChartStore();

  // WebSocket connection
  const { isConnected } = useWebSocket();

  return (
    <div className="app">
      <Toaster position="top-right" />
      
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <h1 className="app-title">Analytical Punch</h1>
          <span className="app-tagline">Professional Trading Analysis</span>
        </div>
        
        <div className="header-controls">
          <TickerSelector />
          <TimeframeSelector />
          
          <div className="connection-status">
            <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`} />
            <span>{isConnected ? 'Live' : 'Offline'}</span>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="app-nav">
        <button 
          className={`nav-tab ${activeTab === 'chart' ? 'active' : ''}`}
          onClick={() => setActiveTab('chart')}
        >
          Chart Analysis
        </button>
        <button 
          className={`nav-tab ${activeTab === 'signals' ? 'active' : ''}`}
          onClick={() => setActiveTab('signals')}
        >
          Trading Signals
        </button>
        <button 
          className={`nav-tab ${activeTab === 'market' ? 'active' : ''}`}
          onClick={() => setActiveTab('market')}
        >
          Market Info
        </button>
        <button 
          className={`nav-tab ${activeTab === 'backtest' ? 'active' : ''}`}
          onClick={() => setActiveTab('backtest')}
        >
          Backtest
        </button>
        <button 
          className={`nav-tab ${activeTab === 'trading' ? 'active' : ''}`}
          onClick={() => setActiveTab('trading')}
        >
          Trading Bots
        </button>
      </nav>

      {/* Main Content */}
      <main className="app-main">
        {error && (
          <div className="error-banner">
            <span>Error: {error}</span>
          </div>
        )}

        {isLoading && (
          <div className="loading-overlay">
            <div className="spinner" />
            <span>Loading {selectedSymbol} data...</span>
          </div>
        )}

        <div className="content-grid">
          {/* Main Chart Area */}
          {activeTab === 'chart' && (
            <>
              <div className="chart-section">
                <ChartContainer />
              </div>
              
              <div className="sidebar">
                <MarketInfoPanel />
                <TradeRecommendations limit={3} />
              </div>
            </>
          )}

          {/* Signals Tab */}
          {activeTab === 'signals' && (
            <div className="signals-section">
              <TradeRecommendations />
            </div>
          )}

          {/* Market Info Tab */}
          {activeTab === 'market' && (
            <div className="market-section">
              <MarketInfoPanel detailed={true} />
            </div>
          )}

          {/* Backtest Tab */}
          {activeTab === 'backtest' && (
            <div className="backtest-section">
              <BacktestDashboard />
            </div>
          )}

          {/* Trading Bots Tab */}
          {activeTab === 'trading' && (
            <div className="trading-section">
              <TradingDashboard />
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <div className="footer-left">
          <span>© 2024 Analytical Punch</span>
          <span className="separator">•</span>
          <span className="mode-indicator">
            {process.env.REACT_APP_PERSONAL_MODE === 'true' ? 'Personal Mode' : 'Standard Mode'}
          </span>
        </div>
        
        <div className="footer-right">
          <a href="#" onClick={(e) => { e.preventDefault(); setShowBacktest(!showBacktest); }}>
            Documentation
          </a>
          <span className="separator">•</span>
          <a href="#" onClick={(e) => { e.preventDefault(); window.location.reload(); }}>
            Refresh
          </a>
        </div>
      </footer>
    </div>
  );
}

export default App;