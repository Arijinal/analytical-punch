import React, { useState } from 'react';
import toast from 'react-hot-toast';
import api from '../../services/api';

const AlertCenter = ({ alerts, onAlertAcknowledge }) => {
  const [filter, setFilter] = useState('all');

  const getAlertIcon = (level) => {
    switch (level) {
      case 'emergency': return '🚨';
      case 'critical': return '⚠️';
      case 'warning': return '⚡';
      case 'info': return 'ℹ️';
      default: return '📢';
    }
  };

  const getAlertColor = (level) => {
    switch (level) {
      case 'emergency': return '#ff4757';
      case 'critical': return '#ff6348';
      case 'warning': return '#ffd93d';
      case 'info': return '#74b9ff';
      default: return '#a0a0a0';
    }
  };

  const handleAcknowledge = async (alertId) => {
    try {
      await api.acknowledgeAlert(alertId, 'user');
      toast.success('Alert acknowledged');
      onAlertAcknowledge();
    } catch (error) {
      console.error('Error acknowledging alert:', error);
      toast.error('Failed to acknowledge alert');
    }
  };

  const filteredAlerts = alerts.filter(alert => {
    if (filter === 'all') return true;
    if (filter === 'unacknowledged') return !alert.acknowledged;
    return alert.level === filter;
  });

  const unacknowledgedCount = alerts.filter(a => !a.acknowledged).length;
  const criticalCount = alerts.filter(a => 
    !a.acknowledged && (a.level === 'critical' || a.level === 'emergency')
  ).length;

  return (
    <div className="alert-center">
      <div className="alert-header">
        <h2>Alert Center</h2>
        <div className="alert-stats">
          {unacknowledgedCount > 0 && (
            <span className="stat-badge unacknowledged">
              {unacknowledgedCount} New
            </span>
          )}
          {criticalCount > 0 && (
            <span className="stat-badge critical">
              {criticalCount} Critical
            </span>
          )}
        </div>
      </div>

      <div className="alert-filters">
        <button
          className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All ({alerts.length})
        </button>
        <button
          className={`filter-btn ${filter === 'unacknowledged' ? 'active' : ''}`}
          onClick={() => setFilter('unacknowledged')}
        >
          Unacknowledged ({unacknowledgedCount})
        </button>
        <button
          className={`filter-btn ${filter === 'emergency' ? 'active' : ''}`}
          onClick={() => setFilter('emergency')}
        >
          Emergency
        </button>
        <button
          className={`filter-btn ${filter === 'critical' ? 'active' : ''}`}
          onClick={() => setFilter('critical')}
        >
          Critical
        </button>
        <button
          className={`filter-btn ${filter === 'warning' ? 'active' : ''}`}
          onClick={() => setFilter('warning')}
        >
          Warning
        </button>
      </div>

      <div className="alert-list">
        {filteredAlerts.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">🔔</span>
            <h3>No alerts</h3>
            <p>All systems operating normally</p>
          </div>
        ) : (
          filteredAlerts.map((alert) => (
            <div
              key={alert.id}
              className={`alert-item ${alert.level} ${alert.acknowledged ? 'acknowledged' : ''}`}
              style={{ borderLeftColor: getAlertColor(alert.level) }}
            >
              <div className="alert-icon">
                {getAlertIcon(alert.level)}
              </div>
              
              <div className="alert-content">
                <div className="alert-header-row">
                  <span className="alert-type">{alert.alert_type}</span>
                  <span className="alert-time">
                    {new Date(alert.timestamp).toLocaleString()}
                  </span>
                </div>
                
                <div className="alert-message">{alert.message}</div>
                
                {alert.details && (
                  <div className="alert-details">
                    <strong>Details:</strong> {JSON.stringify(alert.details)}
                  </div>
                )}
                
                {alert.bot_id && (
                  <div className="alert-bot">
                    <strong>Bot:</strong> {alert.bot_id}
                  </div>
                )}
              </div>
              
              {!alert.acknowledged && (
                <div className="alert-actions">
                  <button
                    className="acknowledge-btn"
                    onClick={() => handleAcknowledge(alert.id)}
                  >
                    Acknowledge
                  </button>
                </div>
              )}
              
              {alert.acknowledged && (
                <div className="alert-acknowledged">
                  <span className="check-icon">✓</span>
                  <span className="acknowledged-info">
                    Acknowledged by {alert.acknowledged_by}
                  </span>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default AlertCenter;