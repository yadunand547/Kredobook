import React from 'react';

/**
 * HealthCard Component
 * Displays system connectivity status for Backend API and Neon PostgreSQL
 */
export function HealthCard({ health, loading, error, lastChecked, onRefresh }) {
  const isBackendConnected = Boolean(health && health.status === 'ok');
  const isDbConnected = Boolean(health && health.database === 'connected');

  return (
    <div className="status-card">
      <div className="card-header">
        <div className="card-title-group">
          <span className="card-badge">System Diagnostics</span>
          <h2 className="card-heading">Service Health Check</h2>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="refresh-btn"
          title="Refresh Status"
          aria-label="Refresh status"
        >
          <svg
            className={`refresh-icon ${loading ? 'spinning' : ''}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
          </svg>
          <span>{loading ? 'Checking...' : 'Refresh'}</span>
        </button>
      </div>

      <div className="services-grid">
        {/* Backend API Item */}
        <div className={`service-item ${isBackendConnected ? 'online' : 'offline'}`}>
          <div className="service-info">
            <div className="service-icon-box">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
                <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
                <line x1="6" y1="6" x2="6.01" y2="6" />
                <line x1="6" y1="18" x2="6.01" y2="18" />
              </svg>
            </div>
            <div>
              <span className="service-name">FastAPI Backend</span>
              <span className="service-subtext">REST API Service</span>
            </div>
          </div>
          <div className="status-indicator">
            <span className={`status-dot ${isBackendConnected ? 'dot-green' : 'dot-red'}`}></span>
            <span className="status-text">
              {isBackendConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>

        {/* Database Item */}
        <div className={`service-item ${isDbConnected ? 'online' : 'offline'}`}>
          <div className="service-info">
            <div className="service-icon-box">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <ellipse cx="12" cy="5" rx="9" ry="3" />
                <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
              </svg>
            </div>
            <div>
              <span className="service-name">Neon PostgreSQL</span>
              <span className="service-subtext">Cloud Database</span>
            </div>
          </div>
          <div className="status-indicator">
            <span className={`status-dot ${isDbConnected ? 'dot-green' : 'dot-red'}`}></span>
            <span className="status-text">
              {isDbConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <div>
            <strong>Connection Notice:</strong> {error}
          </div>
        </div>
      )}

      {lastChecked && (
        <div className="timestamp-footer">
          Last checked at: {lastChecked.toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
