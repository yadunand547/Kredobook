import React, { useState, useEffect } from 'react';
import { NavLink, Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { fetchPendingPayments } from '../services/payments';

export function Navbar() {
  const { currentUser, isAuthenticated, role, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [theme, setTheme] = useState(() => localStorage.getItem('kredobook-theme') || 'light');

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('kredobook-theme', theme);
  }, [theme]);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  // Fetch pending payments count for Admin badge
  useEffect(() => {
    if (isAuthenticated && role === 'ADMIN') {
      fetchPendingPayments()
        .then((data) => setPendingCount(data.length))
        .catch(() => {});
    }
  }, [isAuthenticated, role, location.pathname]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <nav className="app-navbar">
      <div className="navbar-container">
        <Link to={isAuthenticated ? (role === 'ADMIN' ? '/admin' : '/borrower') : '/login'} className="navbar-brand">
          <div className="brand-logo-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className="brand-title">KredoBook</span>
        </Link>

        {/* Desktop Navigation Links */}
        {isAuthenticated && (
          <div className="nav-links-desktop">
            {role === 'ADMIN' ? (
              <>
                <NavLink
                  to="/admin"
                  end
                  className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
                >
                  Dashboard
                </NavLink>
                <NavLink
                  to="/admin/borrowers"
                  className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
                >
                  Borrowers
                </NavLink>
                <NavLink
                  to="/admin/loans"
                  className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
                >
                  Loans
                </NavLink>
                <NavLink
                  to="/admin/payments"
                  className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
                >
                  Payments
                  {pendingCount > 0 && <span className="nav-badge">{pendingCount}</span>}
                </NavLink>
              </>
            ) : (
              <>
                <NavLink
                  to="/borrower"
                  end
                  className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
                >
                  Dashboard
                </NavLink>
                <NavLink
                  to="/borrower/loans"
                  className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
                >
                  My Loans
                </NavLink>
                <NavLink
                  to="/borrower/payments"
                  className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
                >
                  Payment History
                </NavLink>
              </>
            )}
          </div>
        )}

        {/* User Badge & Actions */}
        <div className="navbar-actions">
          <button
            type="button"
            className="theme-toggle"
            onClick={() => setTheme((current) => current === 'light' ? 'dark' : 'light')}
            aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
            title={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
          >
            {theme === 'light' ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
              </svg>
            )}
          </button>
          {isAuthenticated ? (
            <div className="user-nav-group">
              <div className="user-profile-badge">
                <span className="user-name">{currentUser?.name}</span>
                <span className={`role-badge ${role === 'ADMIN' ? 'badge-admin' : 'badge-borrower'}`}>
                  {role}
                </span>
              </div>
              <button onClick={handleLogout} className="logout-btn" title="Sign out">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                <span>Logout</span>
              </button>
            </div>
          ) : (
            <div className="auth-nav-group">
              <Link to="/login" className="login-nav-btn">
                Sign In
              </Link>
            </div>
          )}

          {/* Mobile Hamburger Button */}
          {isAuthenticated && (
            <button
              className="mobile-menu-btn"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle navigation menu"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="22" height="22">
                {mobileMenuOpen ? (
                  <path d="M18 6L6 18M6 6l12 12" />
                ) : (
                  <path d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {isAuthenticated && mobileMenuOpen && (
        <div className="mobile-nav-drawer">
          <div className="mobile-nav-links">
            {role === 'ADMIN' ? (
              <>
                <NavLink
                  to="/admin"
                  end
                  className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
                >
                  Dashboard
                </NavLink>
                <NavLink
                  to="/admin/borrowers"
                  className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
                >
                  Borrowers
                </NavLink>
                <NavLink
                  to="/admin/loans"
                  className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
                >
                  Loans
                </NavLink>
                <NavLink
                  to="/admin/payments"
                  className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
                >
                  Payments {pendingCount > 0 && `(${pendingCount})`}
                </NavLink>
              </>
            ) : (
              <>
                <NavLink
                  to="/borrower"
                  end
                  className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
                >
                  Dashboard
                </NavLink>
                <NavLink
                  to="/borrower/loans"
                  className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
                >
                  My Loans
                </NavLink>
                <NavLink
                  to="/borrower/payments"
                  className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
                >
                  Payment History
                </NavLink>
              </>
            )}
            <button onClick={handleLogout} className="mobile-logout-btn">
              Sign Out
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}
