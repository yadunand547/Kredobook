import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useHealth } from '../hooks/useHealth';
import { HealthCard } from '../components/HealthCard';

export function HomePage() {
  const { health, loading, error, lastChecked, refetch } = useHealth();
  const { isAuthenticated, role, currentUser } = useAuth();

  const dashboardPath = role === 'ADMIN' ? '/admin' : '/borrower';

  return (
    <div className="home-container">
      <header className="hero-section">
        <div className="hero-badge">Smart Loan Management</div>
        <h1 className="hero-title">KredoBook</h1>
        <p className="hero-description">
          Enterprise loan lifecycle management with secure role-based access, automated payment reminders, and Neon PostgreSQL.
        </p>

        <div className="hero-actions">
          {isAuthenticated ? (
            <Link to={dashboardPath} className="hero-btn-primary">
              <span>Go to {role === 'ADMIN' ? 'Admin' : 'Borrower'} Dashboard</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </Link>
          ) : (
            <Link to="/login" className="hero-btn-primary">
              <span>Sign In to Your Account</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </Link>
          )}
        </div>
      </header>

      <main className="main-content">
        <HealthCard
          health={health}
          loading={loading}
          error={error}
          lastChecked={lastChecked}
          onRefresh={refetch}
        />

        <div className="system-overview-card">
          <h3 className="overview-title">Authentication & Security Spec</h3>
          <div className="specs-grid">
            <div className="spec-badge">
              <span className="spec-label">Auth Protocol</span>
              <span className="spec-val">JWT Bearer (HS256)</span>
            </div>
            <div className="spec-badge">
              <span className="spec-label">Hashing</span>
              <span className="spec-val">Bcrypt Salted</span>
            </div>
            <div className="spec-badge">
              <span className="spec-label">Roles</span>
              <span className="spec-val">ADMIN / BORROWER</span>
            </div>
            <div className="spec-badge">
              <span className="spec-label">Access Control</span>
              <span className="spec-val">Backend Enforced</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
