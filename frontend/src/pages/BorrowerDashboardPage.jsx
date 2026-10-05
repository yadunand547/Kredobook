import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { fetchMyLoans, fetchMyStats } from '../services/loans';
import {
  fetchMyPayments,
  submitPayment,
  fetchScreenshotBlobUrl,
} from '../services/payments';

function formatCurrency(val) {
  const n = Number(val || 0);
  return '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'];
    if (typeof dateStr === 'string' && /^\d{4}-\d{2}-\d{2}/.test(dateStr)) {
      const parts = dateStr.slice(0, 10).split('-');
      const y = parseInt(parts[0], 10);
      const m = parseInt(parts[1], 10);
      const d = parseInt(parts[2], 10);
      if (m >= 1 && m <= 12 && d >= 1 && d <= 31) {
        return `${d} ${months[m - 1]} ${y}`;
      }
    }
    const dt = new Date(dateStr);
    if (!isNaN(dt.getTime())) {
      return `${dt.getDate()} ${months[dt.getMonth()]} ${dt.getFullYear()}`;
    }
    return dateStr;
  } catch {
    return dateStr;
  }
}

function getCurrentMonthString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  return `${year}-${month}`;
}

function getCurrentDateString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function sortLoans(loans, sortBy) {
  const sorted = [...loans];
  const amount = (loan) => Number(loan.loan_amount || 0);
  const date = (loan) => new Date(loan.loan_date || loan.created_at || 0).getTime();
  const comparators = {
    newest: (a, b) => date(b) - date(a),
    oldest: (a, b) => date(a) - date(b),
    largest: (a, b) => amount(b) - amount(a),
    smallest: (a, b) => amount(a) - amount(b),
  };
  return sorted.sort(comparators[sortBy] || comparators.newest);
}

export function BorrowerDashboardPage({ initialTab = 'dashboard' }) {
  const { currentUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Active tab: 'dashboard' | 'loans' | 'payments'
  const [activeTab, setActiveTab] = useState(initialTab);

  useEffect(() => {
    if (location.pathname === '/borrower/loans') setActiveTab('loans');
    else if (location.pathname === '/borrower/payments') setActiveTab('payments');
    else if (location.pathname === '/borrower') setActiveTab('dashboard');
  }, [location.pathname]);

  const switchTab = (tab) => {
    setActiveTab(tab);
    if (tab === 'dashboard') navigate('/borrower');
    else if (tab === 'loans') navigate('/borrower/loans');
    else if (tab === 'payments') navigate('/borrower/payments');
  };

  // Data states
  const [loans, setLoans] = useState([]);
  const [payments, setPayments] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [loanSort, setLoanSort] = useState('newest');

  // Modals
  const [selectedLoan, setSelectedLoan] = useState(null);
  const [paymentModalLoan, setPaymentModalLoan] = useState(null);
  const [viewingProofPayment, setViewingProofPayment] = useState(null);

  // Screenshot blob states
  const [screenshotUrl, setScreenshotUrl] = useState(null);
  const [screenshotLoading, setScreenshotLoading] = useState(false);
  const [screenshotError, setScreenshotError] = useState(null);

  // Form states for Make Payment
  const [paymentForm, setPaymentForm] = useState({
    amount: '',
    payment_month: getCurrentMonthString(),
    payment_date: getCurrentDateString(),
    screenshotFile: null,
  });
  const [filePreview, setFilePreview] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const flash = (msg) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 6000);
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [loansData, statsData, paymentsData] = await Promise.all([
        fetchMyLoans(),
        fetchMyStats(),
        fetchMyPayments(),
      ]);
      setLoans(loansData);
      setStats(statsData);
      setPayments(paymentsData);
    } catch (err) {
      setError(err.message || 'Failed to load your loan information.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Load screenshot when viewing proof
  useEffect(() => {
    let active = true;
    if (viewingProofPayment) {
      setScreenshotLoading(true);
      setScreenshotError(null);
      setScreenshotUrl(null);
      fetchScreenshotBlobUrl(viewingProofPayment.id)
        .then((url) => {
          if (active) {
            setScreenshotUrl(url);
            setScreenshotLoading(false);
          }
        })
        .catch((err) => {
          if (active) {
            setScreenshotError(err.message || 'Failed to load screenshot.');
            setScreenshotLoading(false);
          }
        });
    } else {
      if (screenshotUrl) {
        URL.revokeObjectURL(screenshotUrl);
      }
      setScreenshotUrl(null);
    }
    return () => {
      active = false;
    };
  }, [viewingProofPayment]);

  // Derived financial metrics
  const totalBorrowed = loans.reduce((acc, l) => acc + Number(l.loan_amount || 0), 0);
  const totalRepaid = loans.reduce((acc, l) => acc + Number(l.total_paid || 0), 0);
  const sortedLoans = sortLoans(loans, loanSort);
  const activeLoansList = sortedLoans.filter((l) => l.status === 'ACTIVE');
  const paymentAmount = Number(paymentForm.amount);
  const remainingPaymentBalance = Number(paymentModalLoan?.remaining_balance || 0);
  const isFinalPayment = paymentAmount > 0 && paymentAmount >= remainingPaymentBalance;

  // Open Payment Modal
  const openPaymentModal = (loan) => {
    setPaymentModalLoan(loan);
    const minPay = Number(loan.minimum_monthly_payment || 0);
    const remaining = Number(loan.remaining_balance || 0);
    const defaultAmount = remaining > 0 ? Math.min(minPay, remaining) : '';

    setPaymentForm({
      amount: defaultAmount ? String(defaultAmount) : '',
      payment_month: getCurrentMonthString(),
      payment_date: getCurrentDateString(),
      screenshotFile: null,
    });
    setFilePreview(null);
    setFormError(null);
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        setFormError('File size exceeds 5MB limit. Please choose a smaller image.');
        return;
      }
      setPaymentForm((prev) => ({ ...prev, screenshotFile: file }));
      setFilePreview(URL.createObjectURL(file));
      setFormError(null);
    }
  };

  const handleSubmitPayment = async (e) => {
    e.preventDefault();
    setFormError(null);

    if (!paymentForm.screenshotFile) {
      setFormError('Please upload a screenshot of your payment transfer.');
      return;
    }

    const payAmount = Number(paymentForm.amount);
    const maxRemaining = Number(paymentModalLoan?.remaining_balance || 0);

    if (payAmount <= 0) {
      setFormError('Payment amount must be greater than zero.');
      return;
    }
    if (payAmount > maxRemaining) {
      setFormError(
        `Payment amount (${formatCurrency(payAmount)}) exceeds remaining balance of ${formatCurrency(maxRemaining)}.`
      );
      return;
    }

    setSubmitting(true);
    try {
      await submitPayment({
        loan_id: paymentModalLoan.id,
        amount: payAmount,
        payment_month: paymentForm.payment_month,
        payment_date: paymentForm.payment_date,
        screenshotFile: paymentForm.screenshotFile,
      });

      setPaymentModalLoan(null);
      flash(
        `Payment of ${formatCurrency(payAmount)} submitted successfully! Status: PENDING. Your payment will affect the loan balance after admin verification.`
      );
      await loadData();
    } catch (err) {
      setFormError(err.message || 'Payment submission failed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="dashboard-page">
      {/* ── Page Hero Header ──────────────────────────────────────── */}
      <header className="dashboard-hero">
        <div className="dashboard-role-tag">KredoBook Borrower Portal</div>
        <h1 className="dashboard-title">
          {activeTab === 'dashboard' && 'KredoBook Dashboard'}
          {activeTab === 'loans' && 'My Loan Portfolio'}
          {activeTab === 'payments' && 'Payment History'}
        </h1>
        <p className="dashboard-welcome">
          Welcome back, <strong>{currentUser?.name}</strong> •{' '}
          <span className="text-muted">{currentUser?.email}</span>
        </p>
      </header>

      {/* ── Feedback Banners ──────────────────────────────────────── */}
      {successMsg && (
        <div className="alert-banner alert-success" role="status">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="alert-icon">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="alert-banner alert-error" role="alert">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="alert-icon">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
          </svg>
          <span>{error}</span>
          <button className="btn-sm btn-ghost" onClick={loadData}>
            Retry
          </button>
        </div>
      )}

      {/* ── View Navigation Tabs ──────────────────────────────────── */}
      <div className="tabs-nav">
        <button
          className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => switchTab('dashboard')}
        >
          Dashboard Overview
        </button>
        <button
          className={`tab-btn ${activeTab === 'loans' ? 'active' : ''}`}
          onClick={() => switchTab('loans')}
        >
          My Loans ({loans.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'payments' ? 'active' : ''}`}
          onClick={() => switchTab('payments')}
        >
          Payment History ({payments.length})
        </button>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          VIEW 1: BORROWER DASHBOARD OVERVIEW
      ═══════════════════════════════════════════════════════════════ */}
      {activeTab === 'dashboard' && (
        <div className="borrower-dashboard-overview">
          {/* Financial Summary Cards */}
          <section className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon-wrap icon-indigo">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="stat-icon">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
              </div>
              <div className="stat-content">
                <span className="stat-label">Active Loans</span>
                <span className="stat-value">{stats ? stats.active_loans : loading ? '—' : 0}</span>
                <span className="stat-hint">{loans.length} total loan records</span>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon-wrap icon-amber">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="stat-icon">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              </div>
              <div className="stat-content">
                <span className="stat-label">Total Outstanding</span>
                <span className="stat-value stat-highlight">
                  {stats ? formatCurrency(stats.total_outstanding) : loading ? '—' : '₹0.00'}
                </span>
                <span className="stat-hint">Current balance to clear</span>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon-wrap icon-green">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="stat-icon">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              </div>
              <div className="stat-content">
                <span className="stat-label">Total Paid</span>
                <span className="stat-value text-success">
                  {loading ? '—' : formatCurrency(totalRepaid)}
                </span>
                <span className="stat-hint">Verified repayments</span>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon-wrap icon-cyan">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="stat-icon">
                  <line x1="12" y1="1" x2="12" y2="23" />
                  <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                </svg>
              </div>
              <div className="stat-content">
                <span className="stat-label">Total Borrowed</span>
                <span className="stat-value">{loading ? '—' : formatCurrency(totalBorrowed)}</span>
                <span className="stat-hint">Cumulative principal</span>
              </div>
            </div>
          </section>

          {/* Dedicated Separate Active Loan Cards */}
          <section className="dashboard-section card">
            <div className="card-top-bar">
              <div>
                <span className="section-eyebrow">Active Accounts</span>
                <h2 className="section-title">My Active Loans ({activeLoansList.length})</h2>
                <p className="section-desc">Each loan is tracked independently with remaining balance and repayment actions</p>
              </div>
              <div className="loan-toolbar-actions">
                <label className="compact-sort-control">
                  <span>Sort loans</span>
                  <select
                    className="form-input"
                    value={loanSort}
                    onChange={(event) => setLoanSort(event.target.value)}
                  >
                    <option value="newest">Newest first</option>
                    <option value="oldest">Oldest first</option>
                    <option value="largest">Highest amount</option>
                    <option value="smallest">Lowest amount</option>
                  </select>
                </label>
                <button className="btn-sm btn-ghost" onClick={loadData} disabled={loading}>
                  {loading ? 'Refreshing...' : 'Refresh'}
                </button>
              </div>
            </div>

            {loading ? (
              <div className="loading-state">
                <div className="spinner" />
                <p>Loading your active loans...</p>
              </div>
            ) : activeLoansList.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="2" y="5" width="20" height="14" rx="2" />
                    <line x1="2" y1="10" x2="22" y2="10" />
                  </svg>
                </div>
                <h3>No Active Loans</h3>
                <p>You currently do not have any active loans with an outstanding balance.</p>
              </div>
            ) : (
              <div className="loan-cards-grid">
                {activeLoansList.map((loan) => {
                  const paid = Number(loan.total_paid || 0);
                  const payable = Number(loan.total_payable || 1);
                  const progressPct = Math.min(100, Math.round((paid / payable) * 100));

                  return (
                    <div key={loan.id} className="borrower-loan-card">
                      <div className="borrower-loan-card-header">
                        <div>
                          <span className="loan-badge">Loan #{loan.id}</span>
                          <span className="loan-issue-date">Issued {formatDate(loan.loan_date)}</span>
                        </div>
                        <span className="status-pill pill-active">ACTIVE</span>
                      </div>

                      <div className="borrower-loan-card-body">
                        <div className="loan-metric-pair">
                          <div>
                            <span className="metric-title">Original Amount</span>
                            <span className="metric-val font-mono">{formatCurrency(loan.loan_amount)}</span>
                          </div>
                          <div>
                            <span className="metric-title">Total Payable</span>
                            <span className="metric-val font-mono">{formatCurrency(loan.total_payable)}</span>
                          </div>
                        </div>

                        <div className="repayment-progress-compact">
                          <div className="progress-labels">
                            <span style={{ fontSize: '0.8rem' }}>Paid: {formatCurrency(loan.total_paid)}</span>
                            <span className="font-mono" style={{ fontSize: '0.8rem' }}>{progressPct}%</span>
                          </div>
                          <div className="progress-bar-wrap">
                            <div className="progress-bar-fill" style={{ width: `${progressPct}%` }} />
                          </div>
                        </div>

                        <div className="loan-remaining-banner">
                          <span className="rem-label">Remaining Balance</span>
                          <span className="rem-val text-highlight font-mono">
                            {formatCurrency(loan.remaining_balance)}
                          </span>
                        </div>

                        <div className="loan-min-monthly-note">
                          <span>Min Monthly Guidance: </span>
                          <strong className="font-mono">{formatCurrency(loan.minimum_monthly_payment)}</strong>
                        </div>
                      </div>

                      <div className="borrower-loan-card-footer">
                        <button
                          className="submit-btn"
                          style={{
                            flex: 1,
                            padding: '10px 16px',
                            fontSize: '0.9rem',
                            background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                          }}
                          onClick={() => openPaymentModal(loan)}
                        >
                          Make Payment
                        </button>
                        <button
                          className="btn-secondary"
                          style={{ padding: '10px 16px', fontSize: '0.9rem' }}
                          onClick={() => setSelectedLoan(loan)}
                        >
                          Details
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* Recent Submissions Summary */}
          {payments.length > 0 && (
            <section className="dashboard-section card">
              <div className="card-top-bar">
                <div>
                  <span className="section-eyebrow">Recent Activity</span>
                  <h2 className="section-title">Latest Repayment Submissions</h2>
                  <p className="section-desc">Track status and review verification progress</p>
                </div>
                <button className="btn-sm btn-ghost" onClick={() => switchTab('payments')}>
                  View All Submissions ({payments.length}) →
                </button>
              </div>

              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Payment ID</th>
                      <th>Target Loan</th>
                      <th>Amount</th>
                      <th>Month</th>
                      <th>Payment Date</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payments.slice(0, 4).map((p) => (
                      <tr key={p.id}>
                        <td className="font-mono text-bold">#{p.id}</td>
                        <td className="font-mono">Loan #{p.loan_id}</td>
                        <td className="font-mono text-bold text-success">{formatCurrency(p.amount)}</td>
                        <td className="font-mono">{p.payment_month}</td>
                        <td>{formatDate(p.payment_date)}</td>
                        <td>
                          <span
                            className={`status-pill ${
                              p.status === 'VERIFIED'
                                ? 'pill-paid'
                                : p.status === 'PENDING'
                                ? 'pill-amber'
                                : 'pill-inactive'
                            }`}
                          >
                            {p.status}
                          </span>
                        </td>
                        <td>
                          <button className="btn-sm btn-outline" onClick={() => setViewingProofPayment(p)}>
                            View Proof
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          VIEW 2: MY LOANS PORTFOLIO
      ═══════════════════════════════════════════════════════════════ */}
      {activeTab === 'loans' && (
        <section className="dashboard-section card">
          <div className="card-top-bar">
            <div>
              <span className="section-eyebrow">Portfolio</span>
              <h2 className="section-title">All Assigned Loans ({loans.length})</h2>
              <p className="section-desc">Full record of all your current and past loan agreements</p>
            </div>
              <div className="loan-toolbar-actions">
                <label className="compact-sort-control">
                  <span>Sort loans</span>
                  <select
                    className="form-input"
                    value={loanSort}
                    onChange={(event) => setLoanSort(event.target.value)}
                  >
                    <option value="newest">Newest first</option>
                    <option value="oldest">Oldest first</option>
                    <option value="largest">Highest amount</option>
                    <option value="smallest">Lowest amount</option>
                  </select>
                </label>
                <button className="btn-sm btn-ghost" onClick={loadData} disabled={loading}>
                  {loading ? 'Refreshing...' : 'Refresh'}
                </button>
              </div>
          </div>

          {loading ? (
            <div className="loading-state">
              <div className="spinner" />
              <p>Loading your loans...</p>
            </div>
          ) : loans.length === 0 ? (
            <div className="empty-state">
              <h3>No Loans Assigned</h3>
              <p>You currently do not have any loans registered with your account.</p>
            </div>
          ) : (
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Loan ID</th>
                    <th>Loan Date</th>
                    <th>Original Amount</th>
                    <th>Total Payable</th>
                    <th>Amount Repaid</th>
                    <th>Remaining Balance</th>
                    <th>Min Monthly</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedLoans.map((loan) => {
                    const paid = Number(loan.total_paid || 0);
                    const payable = Number(loan.total_payable || 1);
                    const progressPct = Math.min(100, Math.round((paid / payable) * 100));
                    const isEligibleForPayment =
                      loan.status === 'ACTIVE' && Number(loan.remaining_balance || 0) > 0;

                    return (
                      <tr key={loan.id}>
                        <td className="font-mono text-bold">#{loan.id}</td>
                        <td>{formatDate(loan.loan_date)}</td>
                        <td className="font-mono">{formatCurrency(loan.loan_amount)}</td>
                        <td className="font-mono">{formatCurrency(loan.total_payable)}</td>
                        <td className="font-mono text-success">
                          <div>{formatCurrency(loan.total_paid)}</div>
                          <div className="progress-bar-wrap">
                            <div className="progress-bar-fill" style={{ width: `${progressPct}%` }} />
                          </div>
                        </td>
                        <td className="font-mono text-bold text-highlight">
                          {formatCurrency(loan.remaining_balance)}
                        </td>
                        <td className="font-mono text-muted">
                          {formatCurrency(loan.minimum_monthly_payment)}
                        </td>
                        <td>
                          <span
                            className={`status-pill ${
                              loan.status === 'ACTIVE'
                                ? 'pill-active'
                                : loan.status === 'PAID'
                                ? 'pill-paid'
                                : 'pill-inactive'
                            }`}
                          >
                            {loan.status}
                          </span>
                        </td>
                        <td>
                          <div className="table-actions">
                            {isEligibleForPayment && (
                              <button
                                className="btn-sm btn-success-action"
                                onClick={() => openPaymentModal(loan)}
                              >
                                Make Payment
                              </button>
                            )}
                            <button
                              className="btn-sm btn-outline"
                              onClick={() => setSelectedLoan(loan)}
                            >
                              Details
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          VIEW 3: PAYMENT HISTORY
      ═══════════════════════════════════════════════════════════════ */}
      {activeTab === 'payments' && (
        <section className="dashboard-section card">
          <div className="card-top-bar">
            <div>
              <span className="section-eyebrow">Payment Verification History</span>
              <h2 className="section-title">My Repayment Submissions ({payments.length})</h2>
              <p className="section-desc">Audit all payment submissions, verification timestamps, and admin review feedback</p>
            </div>
            <button className="btn-sm btn-ghost" onClick={loadData} disabled={loading}>
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          {payments.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M16 16s-1.5-2-4-2-4 2-4 2" />
                  <line x1="9" y1="9" x2="9.01" y2="9" />
                  <line x1="15" y1="9" x2="15.01" y2="9" />
                </svg>
              </div>
              <h3>No Payment Submissions Yet</h3>
              <p>When you submit a loan repayment screenshot, its verification progress will appear here.</p>
            </div>
          ) : (
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Payment ID</th>
                    <th>Target Loan</th>
                    <th>Amount Paid</th>
                    <th>Payment Month</th>
                    <th>Transfer Date</th>
                    <th>Submitted At</th>
                    <th>Status</th>
                    <th>Proof & Verification Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map((p) => (
                    <tr key={p.id}>
                      <td className="font-mono text-bold">#{p.id}</td>
                      <td className="font-mono">
                        <span className="badge-outline">Loan #{p.loan_id}</span>
                      </td>
                      <td className="font-mono text-bold text-success" style={{ fontSize: '1rem' }}>
                        {formatCurrency(p.amount)}
                      </td>
                      <td className="font-mono">{p.payment_month}</td>
                      <td>{formatDate(p.payment_date)}</td>
                      <td className="text-muted" style={{ fontSize: '0.825rem' }}>
                        {new Date(p.submitted_at).toLocaleString()}
                      </td>
                      <td>
                        <span
                          className={`status-pill ${
                            p.status === 'VERIFIED'
                              ? 'pill-paid'
                              : p.status === 'PENDING'
                              ? 'pill-amber'
                              : 'pill-inactive'
                          }`}
                        >
                          {p.status}
                        </span>
                      </td>
                      <td>
                        <div className="table-actions">
                          <button
                            className="btn-sm btn-outline"
                            onClick={() => setViewingProofPayment(p)}
                            title="View uploaded proof screenshot"
                          >
                            View Proof
                          </button>
                          {p.rejection_reason && (
                            <div className="rejection-reason-chip" title={p.rejection_reason}>
                              <span style={{ color: '#fca5a5' }}>Reason: {p.rejection_reason}</span>
                            </div>
                          )}
                          {p.status === 'VERIFIED' && p.verified_at && (
                            <span className="text-muted" style={{ fontSize: '0.8rem' }}>
                              Verified on {new Date(p.verified_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          MODALS
      ═══════════════════════════════════════════════════════════════ */}

      {/* ── MODAL: Make Payment Form ───────────────────────────────── */}
      {paymentModalLoan && (
        <div className="modal-backdrop" onClick={() => !submitting && setPaymentModalLoan(null)}>
          <div className="modal-card payment-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="section-eyebrow">Repayment Submission</span>
                <h3 className="modal-title">Make Payment for Loan #{paymentModalLoan.id}</h3>
              </div>
              <button
                className="modal-close"
                disabled={submitting}
                onClick={() => setPaymentModalLoan(null)}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleSubmitPayment} className="modal-form">
              {formError && (
                <div className="alert-banner alert-error">
                  <span>{formError}</span>
                </div>
              )}

              {/* Loan Context Summary */}
              <div className="highlight-box" style={{ marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span className="hl-label">Remaining Balance:</span>
                  <span className="text-highlight font-mono text-bold" style={{ fontSize: '1.1rem' }}>
                    {formatCurrency(paymentModalLoan.remaining_balance)}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                  <span className="text-muted">Suggested Monthly Amount:</span>
                  <span className="font-mono text-muted">
                    {formatCurrency(paymentModalLoan.minimum_monthly_payment)}
                  </span>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">
                  Payment Amount (₹) *
                  <span className="field-hint" style={{ float: 'right', fontWeight: 'normal', color: 'var(--text-muted)' }}>
                    Max: {formatCurrency(paymentModalLoan.remaining_balance)}
                  </span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={Number(paymentModalLoan.remaining_balance)}
                  required
                  className="form-input"
                  placeholder="e.g. 500 or 1000"
                  value={paymentForm.amount}
                  onChange={(e) => setPaymentForm({ ...paymentForm, amount: e.target.value })}
                />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Any positive amount is accepted, up to the remaining balance.
                </span>
              </div>

              {isFinalPayment && (
                <div className="final-payment-warning" role="alert">
                  <strong>Final payment notice</strong>
                  <span>
                    This payment will settle this loan after it is verified. Please contact customer support to confirm the final amount before transferring, as the closing amount may differ slightly.
                  </span>
                </div>
              )}

              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Payment Month *</label>
                  <input
                    type="month"
                    required
                    className="form-input"
                    value={paymentForm.payment_month}
                    onChange={(e) => setPaymentForm({ ...paymentForm, payment_month: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Transfer Date *</label>
                  <input
                    type="date"
                    required
                    className="form-input"
                    value={paymentForm.payment_date}
                    onChange={(e) => setPaymentForm({ ...paymentForm, payment_date: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Upload Payment Screenshot (UPI / Bank Transfer) *</label>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/jpg,image/webp"
                  required
                  className="form-input"
                  style={{ padding: '8px' }}
                  onChange={handleFileChange}
                />
                {filePreview && (
                  <div className="file-preview-wrap" style={{ marginTop: '10px' }}>
                    <img
                      src={filePreview}
                      alt="Proof Preview"
                      style={{ maxHeight: '160px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}
                    />
                  </div>
                )}
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={submitting}
                  onClick={() => setPaymentModalLoan(null)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="submit-btn"
                  disabled={submitting}
                  style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}
                >
                  {submitting ? 'Submitting Payment...' : 'Submit Payment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── MODAL: View Proof Screenshot ───────────────────────────── */}
      {viewingProofPayment && (
        <div className="modal-backdrop" onClick={() => setViewingProofPayment(null)}>
          <div className="modal-card modal-lg" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="section-eyebrow">Payment Proof #{viewingProofPayment.id}</span>
                <h3 className="modal-title">Payment Screenshot & Details</h3>
              </div>
              <button className="modal-close" onClick={() => setViewingProofPayment(null)}>
                ×
              </button>
            </div>

            <div className="modal-body">
              <div className="loan-detail-highlight-grid">
                <div className="highlight-box">
                  <span className="hl-label">Amount</span>
                  <span className="hl-value text-success">{formatCurrency(viewingProofPayment.amount)}</span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Status</span>
                  <span className="hl-value">
                    <span
                      className={`status-pill ${
                        viewingProofPayment.status === 'VERIFIED'
                          ? 'pill-paid'
                          : viewingProofPayment.status === 'PENDING'
                          ? 'pill-amber'
                          : 'pill-inactive'
                      }`}
                    >
                      {viewingProofPayment.status}
                    </span>
                  </span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Month & Date</span>
                  <span className="hl-value" style={{ fontSize: '1rem' }}>
                    {viewingProofPayment.payment_month} • {formatDate(viewingProofPayment.payment_date)}
                  </span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Target Loan</span>
                  <span className="hl-value" style={{ fontSize: '1rem' }}>
                    Loan #{viewingProofPayment.loan_id}
                  </span>
                </div>
              </div>

              {viewingProofPayment.rejection_reason && (
                <div className="alert-banner alert-error" style={{ marginBottom: '16px' }}>
                  <strong>Admin Rejection Feedback:</strong> {viewingProofPayment.rejection_reason}
                </div>
              )}

              <div className="screenshot-preview-container">
                {screenshotLoading ? (
                  <div className="loading-state">
                    <div className="spinner" />
                    <p>Loading your proof screenshot...</p>
                  </div>
                ) : screenshotError ? (
                  <div className="alert-banner alert-error">
                    <span>{screenshotError}</span>
                  </div>
                ) : screenshotUrl ? (
                  <div className="screenshot-img-wrapper">
                    <img
                      src={screenshotUrl}
                      alt={`Payment ${viewingProofPayment.id} Proof`}
                      className="screenshot-img"
                    />
                  </div>
                ) : null}
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setViewingProofPayment(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Loan Breakdown Details ──────────────────────────── */}
      {selectedLoan && (
        <div className="modal-backdrop" onClick={() => setSelectedLoan(null)}>
          <div className="modal-card modal-lg loan-summary-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="section-eyebrow">Loan #{selectedLoan.id}</span>
                <h3 className="modal-title">Loan Breakdown & Summary</h3>
              </div>
              <button className="modal-close" onClick={() => setSelectedLoan(null)}>
                ×
              </button>
            </div>

            <div className="modal-body">
              <div className="loan-detail-highlight-grid">
                <div className="highlight-box">
                  <span className="hl-label">Originally Borrowed</span>
                  <span className="hl-value">{formatCurrency(selectedLoan.loan_amount)}</span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Total Payable</span>
                  <span className="hl-value">{formatCurrency(selectedLoan.total_payable)}</span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Amount Paid</span>
                  <span className="hl-value text-success">{formatCurrency(selectedLoan.total_paid)}</span>
                </div>
                <div className="highlight-box highlight-accent">
                  <span className="hl-label">Remaining Balance</span>
                  <span className="hl-value text-highlight">
                    {formatCurrency(selectedLoan.remaining_balance)}
                  </span>
                </div>
              </div>

              <div className="repayment-progress-section">
                <div className="progress-labels">
                  <span>Repayment Progress</span>
                  <span className="font-mono">
                    {Math.min(
                      100,
                      Math.round(
                        (Number(selectedLoan.total_paid || 0) /
                          Number(selectedLoan.total_payable || 1)) *
                          100
                      )
                    )}
                    %
                  </span>
                </div>
                <div className="progress-bar-lg">
                  <div
                    className="progress-bar-lg-fill"
                    style={{
                      width: `${Math.min(
                        100,
                        Math.round(
                          (Number(selectedLoan.total_paid || 0) /
                            Number(selectedLoan.total_payable || 1)) *
                            100
                        )
                      )}%`,
                    }}
                  />
                </div>
              </div>

              <div className="loan-meta-grid">
                <div className="meta-item">
                  <span className="meta-label">Minimum Monthly Payment</span>
                  <span className="meta-value font-mono">
                    {formatCurrency(selectedLoan.minimum_monthly_payment)}
                  </span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Loan Date</span>
                  <span className="meta-value">{formatDate(selectedLoan.loan_date)}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Loan Status</span>
                  <span className="meta-value">
                    <span
                      className={`status-pill ${
                        selectedLoan.status === 'ACTIVE'
                          ? 'pill-active'
                          : selectedLoan.status === 'PAID'
                          ? 'pill-paid'
                          : 'pill-inactive'
                      }`}
                    >
                      {selectedLoan.status}
                    </span>
                  </span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Account Name</span>
                  <span className="meta-value">{currentUser?.name}</span>
                </div>
              </div>

              {selectedLoan.notes && (
                <div className="loan-notes-box">
                  <span className="notes-label">Loan Notes</span>
                  <p className="notes-body">{selectedLoan.notes}</p>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setSelectedLoan(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
