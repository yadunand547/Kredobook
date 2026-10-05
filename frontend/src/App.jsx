import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { BorrowerDashboardPage } from './pages/BorrowerDashboardPage';

function RootRedirect() {
  const { isAuthenticated, role, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Verifying authentication...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to={role === 'ADMIN' ? '/admin' : '/borrower'} replace />;
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="app-shell">
          <Navbar />
          <div className="app-main-view">
            <Routes>
              {/* Public Routes */}
              <Route path="/" element={<RootRedirect />} />
              <Route path="/login" element={<LoginPage />} />

              {/* Admin Routes */}
              <Route
                path="/admin"
                element={
                  <ProtectedRoute allowedRoles={['ADMIN']}>
                    <AdminDashboardPage initialTab="dashboard" />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/borrowers"
                element={
                  <ProtectedRoute allowedRoles={['ADMIN']}>
                    <AdminDashboardPage initialTab="borrowers" />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/loans"
                element={
                  <ProtectedRoute allowedRoles={['ADMIN']}>
                    <AdminDashboardPage initialTab="loans" />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/payments"
                element={
                  <ProtectedRoute allowedRoles={['ADMIN']}>
                    <AdminDashboardPage initialTab="payments" />
                  </ProtectedRoute>
                }
              />

              {/* Borrower Routes */}
              <Route
                path="/borrower"
                element={
                  <ProtectedRoute allowedRoles={['BORROWER']}>
                    <BorrowerDashboardPage initialTab="dashboard" />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/borrower/loans"
                element={
                  <ProtectedRoute allowedRoles={['BORROWER']}>
                    <BorrowerDashboardPage initialTab="loans" />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/borrower/payments"
                element={
                  <ProtectedRoute allowedRoles={['BORROWER']}>
                    <BorrowerDashboardPage initialTab="payments" />
                  </ProtectedRoute>
                }
              />

              <Route path="*" element={<RootRedirect />} />

            </Routes>
          </div>
          <footer className="app-footer" style={{ textAlign: 'center', padding: '1.5rem', color: '#64748b', fontSize: '0.85rem', borderTop: '1px solid rgba(255, 255, 255, 0.05)', marginTop: 'auto' }}>
            © KredoBook. All rights reserved.
          </footer>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
