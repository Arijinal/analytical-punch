import React, { useState, useEffect } from 'react';
import './TradingDashboard.css';
import BotList from './BotList';
import BotDetails from './BotDetails';
import BotCreator from './BotCreator';
import SystemMonitor from './SystemMonitor';
import AlertCenter from './AlertCenter';
import api from '../../services/api';

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
      const botsData = await api.getBots();
      setBots(botsData.bots || []);

      // Load system status
      const statusData = await api.getSystemStatus();
      setSystemStatus(statusData);

      // Load alerts
      const alertsData = await api.getAlerts(null, null, true, 20);
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
      await api.createBot(botConfig);
      await loadDashboardData();
      setActiveTab('bots');
    } catch (error) {
      console.error('Error creating bot:', error);
      alert('Failed to create bot: ' + error.message);
    }
  };

  const handleBotAction = async (botId, action) => {
    try {
      // Call the appropriate API method based on action
      switch (action) {
        case 'start':
          await api.startBot(botId);
          break;
        case 'stop':
          await api.stopBot(botId);
          break;
        case 'pause':
          await api.pauseBot(botId);
          break;
        case 'resume':
          await api.resumeBot(botId);
          break;
        default:
          throw new Error(`Unknown action: ${action}`);
      }

      await loadDashboardData();
      // Update selected bot if it's the one being acted upon
      if (selectedBot && selectedBot.bot_id === botId) {
        const updatedBot = bots.find(bot => bot.bot_id === botId);
        setSelectedBot(updatedBot);
      }
    } catch (error) {
      console.error(`Error ${action} bot:`, error);
      alert(`Failed to ${action} bot: ${error.message}`);
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