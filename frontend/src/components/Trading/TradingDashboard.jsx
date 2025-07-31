import React, { useState, useEffect } from 'react';
import './TradingDashboard.css';
import BotList from './BotList';
import BotDetails from './BotDetails';
import BotCreator from './BotCreator';
import SystemMonitor from './SystemMonitor';
import AlertCenter from './AlertCenter';

const TradingDashboard = () => {
  const [activeTab, setActiveTab] = useState('bots');
  const [selectedBot, setSelectedBot] = useState(null);
  const [bots, setBots] = useState([]);
  const [systemStatus, setSystemStatus] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
    const interval = setInterval(loadDashboardData, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      // Load bots
      const botsResponse = await fetch('/api/v1/trading/bots');
      const botsData = await botsResponse.json();
      setBots(botsData);

      // Load system status
      const statusResponse = await fetch('/api/v1/trading/system/status');
      const statusData = await statusResponse.json();
      setSystemStatus(statusData);

      // Load alerts
      const alertsResponse = await fetch('/api/v1/trading/alerts?unacknowledged_only=true&limit=20');
      const alertsData = await alertsResponse.json();
      setAlerts(alertsData);

      setLoading(false);
    } catch (error) {
      console.error('Error loading dashboard data:', error);
      setLoading(false);
    }
  };

  const handleBotSelect = (bot) => {
    setSelectedBot(bot);
    setActiveTab('details');
  };

  const handleBotCreate = async (botConfig) => {
    try {
      const response = await fetch('/api/v1/trading/bots', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(botConfig),
      });

      if (response.ok) {
        await loadDashboardData();
        setActiveTab('bots');
      } else {
        throw new Error('Failed to create bot');
      }
    } catch (error) {
      console.error('Error creating bot:', error);
      alert('Failed to create bot');
    }
  };

  const handleBotAction = async (botId, action) => {
    try {
      const response = await fetch(`/api/v1/trading/bots/${botId}/${action}`, {
        method: 'POST',
      });

      if (response.ok) {
        await loadDashboardData();
        // Update selected bot if it's the one being acted upon
        if (selectedBot && selectedBot.bot_id === botId) {
          const updatedBot = bots.find(bot => bot.bot_id === botId);
          setSelectedBot(updatedBot);
        }
      } else {
        throw new Error(`Failed to ${action} bot`);
      }
    } catch (error) {
      console.error(`Error ${action} bot:`, error);
      alert(`Failed to ${action} bot`);
    }
  };

  const unacknowledgedAlerts = alerts.filter(alert => !alert.acknowledged);
  const criticalAlerts = alerts.filter(alert => 
    alert.level === 'critical' || alert.level === 'emergency'
  );

  if (loading) {
    return (
      <div className="trading-dashboard loading">
        <div className="loading-spinner">Loading Trading Dashboard...</div>
      </div>
    );
  }

  return (
    <div className="trading-dashboard">
      <header className="dashboard-header">
        <h1>Trading Bot Dashboard</h1>
        <div className="header-stats">
          <div className="stat-item">
            <span className="stat-label">Active Bots</span>
            <span className="stat-value">{systemStatus.running_bots || 0}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Total Bots</span>
            <span className="stat-value">{systemStatus.active_bots || 0}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Alerts</span>
            <span className={`stat-value ${criticalAlerts.length > 0 ? 'critical' : ''}`}>
              {unacknowledgedAlerts.length}
            </span>
          </div>
        </div>
      </header>

      <nav className="dashboard-nav">
        <button 
          className={`nav-tab ${activeTab === 'bots' ? 'active' : ''}`}
          onClick={() => setActiveTab('bots')}
        >
          Bot Management
        </button>
        <button 
          className={`nav-tab ${activeTab === 'create' ? 'active' : ''}`}
          onClick={() => setActiveTab('create')}
        >
          Create Bot
        </button>
        <button 
          className={`nav-tab ${activeTab === 'monitor' ? 'active' : ''}`}
          onClick={() => setActiveTab('monitor')}
        >
          System Monitor
        </button>
        <button 
          className={`nav-tab ${activeTab === 'alerts' ? 'active' : ''}`}
          onClick={() => setActiveTab('alerts')}
        >
          Alerts {unacknowledgedAlerts.length > 0 && (
            <span className="alert-badge">{unacknowledgedAlerts.length}</span>
          )}
        </button>
        {selectedBot && (
          <button 
            className={`nav-tab ${activeTab === 'details' ? 'active' : ''}`}
            onClick={() => setActiveTab('details')}
          >
            {selectedBot.name} Details
          </button>
        )}
      </nav>

      <main className="dashboard-content">
        {activeTab === 'bots' && (
          <BotList 
            bots={bots}
            onBotSelect={handleBotSelect}
            onBotAction={handleBotAction}
          />
        )}

        {activeTab === 'create' && (
          <BotCreator onBotCreate={handleBotCreate} />
        )}

        {activeTab === 'details' && selectedBot && (
          <BotDetails 
            bot={selectedBot}
            onBotAction={handleBotAction}
          />
        )}

        {activeTab === 'monitor' && (
          <SystemMonitor 
            systemStatus={systemStatus}
            bots={bots}
          />
        )}

        {activeTab === 'alerts' && (
          <AlertCenter 
            alerts={alerts}
            onAlertAcknowledge={loadDashboardData}
          />
        )}
      </main>
    </div>
  );
};

export default TradingDashboard;