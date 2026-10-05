import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  fetchBorrowers,
  createBorrower,
  updateBorrower,
  deactivateBorrower,
  deleteBorrower,
} from '../services/borrowers';
import {
  fetchLoans,
  createLoan,
  updateLoan,
  deleteLoan,
  fetchAdminDashboardStats,
} from '../services/loans';
import {
  fetchAllPayments,
  fetchPendingPayments,
  approvePayment,
  rejectPayment,
  fetchLoanPayments,
  fetchScreenshotBlobUrl,
  adminRecordPayment,
  updateAdminRecordedPayment,
} from '../services/payments';
import {
  triggerMonthlyReminders,
  toggleBorrowerReminder,
} from '../services/reminders';


function formatCurrency(val) {
  const n = Number(val || 0);
  if (n % 1 === 0) {
    return '₹' + n.toLocaleString('en-IN');
  }
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

function sortLoans(loans, sortBy) {
  const sorted = [...loans];
  const numeric = (loan, field) => Number(loan[field] || 0);
  const dateValue = (loan) => new Date(loan.loan_date || loan.created_at || 0).getTime();
  const comparators = {
    newest: (a, b) => dateValue(b) - dateValue(a),
    oldest: (a, b) => dateValue(a) - dateValue(b),
    largest: (a, b) => numeric(b, 'loan_amount') - numeric(a, 'loan_amount'),
    smallest: (a, b) => numeric(a, 'loan_amount') - numeric(b, 'loan_amount'),
    highest_balance: (a, b) => numeric(b, 'remaining_balance') - numeric(a, 'remaining_balance'),
    lowest_balance: (a, b) => numeric(a, 'remaining_balance') - numeric(b, 'remaining_balance'),
  };
  return sorted.sort(comparators[sortBy] || comparators.newest);
}

function MinimalPagination({
  currentPage,
  totalItems,
  pageSize,
  onPageChange,
  itemLabel = 'items',
}) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  if (totalItems === 0) return null;

  const startIdx = (currentPage - 1) * pageSize + 1;
  const endIdx = Math.min(currentPage * pageSize, totalItems);

  const getPages = () => {
    if (totalPages <= 5) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    if (currentPage <= 3) {
      return [1, 2, 3, 4, '...', totalPages];
    }
    if (currentPage >= totalPages - 2) {
      return [1, '...', totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
    }
    return [1, '...', currentPage - 1, currentPage, currentPage + 1, '...', totalPages];
  };

  const pages = getPages();

  return (
    <div className="table-pagination">
      <div className="pagination-info">
        Showing <span className="text-bold">{startIdx}</span>–<span className="text-bold">{endIdx}</span> of{' '}
        <span className="text-bold">{totalItems}</span> {itemLabel}
      </div>

      <div className="pagination-controls">
        <button
          type="button"
          className="pagination-btn"
          onClick={() => onPageChange(Math.max(currentPage - 1, 1))}
          disabled={currentPage === 1}
          title="Previous page"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          <span>Prev</span>
        </button>

        <div className="pagination-pages">
          {pages.map((p, idx) =>
            p === '...' ? (
              <span key={`ellipsis-${idx}`} className="pagination-ellipsis">
                …
              </span>
            ) : (
              <button
                key={p}
                type="button"
                className={`pagination-page-btn ${p === currentPage ? 'active' : ''}`}
                onClick={() => onPageChange(p)}
              >
                {p}
              </button>
            )
          )}
        </div>

        <button
          type="button"
          className="pagination-btn"
          onClick={() => onPageChange(Math.min(currentPage + 1, totalPages))}
          disabled={currentPage === totalPages}
          title="Next page"
        >
          <span>Next</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export function AdminDashboardPage({ initialTab = 'dashboard' }) {
  const { currentUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Active tab derived from props / path: 'dashboard' | 'borrowers' | 'loans' | 'payments'
  const [activeTab, setActiveTab] = useState(initialTab);

  useEffect(() => {
    if (location.pathname === '/admin/borrowers') setActiveTab('borrowers');
    else if (location.pathname === '/admin/loans') setActiveTab('loans');
    else if (location.pathname === '/admin/payments') setActiveTab('payments');
    else if (location.pathname === '/admin') setActiveTab('dashboard');
  }, [location.pathname]);

  const switchTab = (tab) => {
    setActiveTab(tab);
    if (tab === 'dashboard') navigate('/admin');
    else if (tab === 'borrowers') navigate('/admin/borrowers');
    else if (tab === 'loans') navigate('/admin/loans');
    else if (tab === 'payments') navigate('/admin/payments');
  };

  // Data states
  const [stats, setStats] = useState(null);
  const [borrowers, setBorrowers] = useState([]);
  const [loans, setLoans] = useState([]);
  const [allPayments, setAllPayments] = useState([]);
  const [pendingPayments, setPendingPayments] = useState([]);

  // Payment filter in Payments page: 'PENDING' | 'VERIFIED' | 'REJECTED' | 'ALL'
  const [paymentFilter, setPaymentFilter] = useState('PENDING');
  const [loanSort, setLoanSort] = useState('newest');
  const [loanBorrowerFilter, setLoanBorrowerFilter] = useState('ALL');
  const [borrowerFilter, setBorrowerFilter] = useState('ALL');
  const [borrowerSearch, setBorrowerSearch] = useState('');

  // Loading states
  const [statsLoading, setStatsLoading] = useState(true);
  const [borrowersLoading, setBorrowersLoading] = useState(false);
  const [loansLoading, setLoansLoading] = useState(false);
  const [paymentsLoading, setPaymentsLoading] = useState(false);

  // Modals
  const [showBorrowerModal, setShowBorrowerModal] = useState(false);
  const [showLoanModal, setShowLoanModal] = useState(false);
  const [showLoanDetail, setShowLoanDetail] = useState(null);
  const [loanPaymentsHistory, setLoanPaymentsHistory] = useState([]);
  const [loanPaymentsLoading, setLoanPaymentsLoading] = useState(false);
  const [editingLoan, setEditingLoan] = useState(null);

  // Borrower details modal
  const [viewingBorrower, setViewingBorrower] = useState(null);
  const [borrowerLoans, setBorrowerLoans] = useState([]);

  // Payment review modal states
  const [reviewingPayment, setReviewingPayment] = useState(null);
  const [screenshotUrl, setScreenshotUrl] = useState(null);
  const [screenshotLoading, setScreenshotLoading] = useState(false);
  const [screenshotError, setScreenshotError] = useState(null);

  const [approvingPayment, setApprovingPayment] = useState(null);
  const [rejectingPayment, setRejectingPayment] = useState(null);
  const [rejectionReason, setRejectionReason] = useState('');

  // Form states
  const [borrowerForm, setBorrowerForm] = useState({ name: '', email: '', phone: '', password: '' });
  const [loanForm, setLoanForm] = useState({
    borrower_id: '',
    loan_amount: '',
    loan_date: '',
    total_payable: '',
    minimum_monthly_payment: '',
    notes: '',
  });
  const [editLoanForm, setEditLoanForm] = useState({});
  const [showPastPaymentModal, setShowPastPaymentModal] = useState(false);
  const [pastPaymentLoan, setPastPaymentLoan] = useState(null);
  const [editingPastPayment, setEditingPastPayment] = useState(null);
  const [pastPaymentForm, setPastPaymentForm] = useState({
    amount: '',
    payment_month: new Date().toISOString().slice(0, 7),
    payment_date: new Date().toISOString().slice(0, 10),
    notes: '',
  });

  // Modern pagination states
  const [borrowersPage, setBorrowersPage] = useState(1);
  const borrowersPerPage = 8;
  const [loansPage, setLoansPage] = useState(1);
  const loansPerPage = 8;
  const [paymentsPage, setPaymentsPage] = useState(1);
  const paymentsPerPage = 8;

  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [error, setError] = useState(null);

  const flash = (msg) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 4000);
  };

  // Data loaders
  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      setStats(await fetchAdminDashboardStats());
    } catch {
      /* ignore */
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const loadBorrowers = useCallback(async () => {
    setBorrowersLoading(true);
    try {
      setBorrowers(await fetchBorrowers());
    } catch (e) {
      setError(e.message);
    } finally {
      setBorrowersLoading(false);
    }
  }, []);

  const loadLoans = useCallback(async () => {
    setLoansLoading(true);
    try {
      setLoans(await fetchLoans());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoansLoading(false);
    }
  }, []);

  const loadPayments = useCallback(async () => {
    setPaymentsLoading(true);
    try {
      const [pending, all] = await Promise.all([
        fetchPendingPayments(),
        fetchAllPayments(),
      ]);
      setPendingPayments(pending);
      setAllPayments(all);
    } catch (e) {
      setError(e.message);
    } finally {
      setPaymentsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStats();
    loadBorrowers();
    loadLoans();
    loadPayments();
  }, [loadStats, loadBorrowers, loadLoans, loadPayments]);

  // Load screenshot when reviewing payment
  useEffect(() => {
    let active = true;
    if (reviewingPayment) {
      setScreenshotLoading(true);
      setScreenshotError(null);
      setScreenshotUrl(null);
      fetchScreenshotBlobUrl(reviewingPayment.id)
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
  }, [reviewingPayment]);

  // Open Borrower Details Modal
  const openBorrowerDetail = (borrower) => {
    setViewingBorrower(borrower);
    const assigned = loans.filter((l) => l.borrower_id === borrower.id);
    setBorrowerLoans(assigned);
  };

  // Open Loan Details Modal
  const openLoanDetail = async (loan) => {
    setShowLoanDetail(loan);
    setLoanPaymentsLoading(true);
    try {
      const history = await fetchLoanPayments(loan.id);
      setLoanPaymentsHistory(history);
    } catch {
      setLoanPaymentsHistory([]);
    } finally {
      setLoanPaymentsLoading(false);
    }
  };

  // Open Record Past Payment Modal
  const openRecordPastPayment = (loan) => {
    setEditingPastPayment(null);
    setPastPaymentLoan(loan);
    const today = new Date().toISOString().slice(0, 10);
    const thisMonth = today.slice(0, 7);
    setPastPaymentForm({
      amount: '',
      payment_month: thisMonth,
      payment_date: today,
      notes: 'Paid before KredoBook platform setup',
    });
    setFormError(null);
    setShowPastPaymentModal(true);
  };

  const openEditPastPayment = (payment) => {
    const loan = loans.find((item) => item.id === payment.loan_id);
    if (!loan) {
      setError('Loan details are not available. Please refresh and try again.');
      return;
    }
    setPastPaymentLoan(loan);
    setEditingPastPayment(payment);
    setPastPaymentForm({
      amount: String(payment.amount),
      payment_month: payment.payment_month,
      payment_date: String(payment.payment_date).slice(0, 10),
      notes: payment.rejection_reason || '',
    });
    setFormError(null);
    setShowPastPaymentModal(true);
  };

  // Submit Admin Past Payment
  const handleRecordPastPayment = async (e) => {
    e.preventDefault();
    setFormError(null);
    setFormSubmitting(true);
    try {
      const amt = parseFloat(pastPaymentForm.amount);
      if (!amt || amt <= 0) {
        throw new Error('Please enter an amount greater than 0');
      }
      const maxAmount = editingPastPayment
        ? Number(pastPaymentLoan.remaining_balance) + Number(editingPastPayment.amount)
        : Number(pastPaymentLoan.remaining_balance);
      if (amt > maxAmount) {
        throw new Error(`Amount cannot exceed remaining balance of ₹${Number(pastPaymentLoan.remaining_balance).toLocaleString('en-IN')}`);
      }
      if (editingPastPayment) {
        await updateAdminRecordedPayment(editingPastPayment.id, {
          amount: amt,
          payment_month: pastPaymentForm.payment_month,
          payment_date: pastPaymentForm.payment_date,
          notes: pastPaymentForm.notes || undefined,
        });
        flash(`Past payment #${editingPastPayment.id} updated successfully.`);
      } else {
        await adminRecordPayment({
        loan_id: pastPaymentLoan.id,
        amount: amt,
        payment_month: pastPaymentForm.payment_month,
        payment_date: pastPaymentForm.payment_date,
        notes: pastPaymentForm.notes || undefined,
      });
      flash(`Payment of ₹${amt.toLocaleString('en-IN')} recorded successfully for Loan #${pastPaymentLoan.id}!`);
      }
      setShowPastPaymentModal(false);
      setEditingPastPayment(null);

      // Refresh data
      await Promise.all([loadLoans(), loadStats(), loadPayments()]);

      // If viewing loan details for this loan, refresh its details and history
      if (showLoanDetail && showLoanDetail.id === pastPaymentLoan.id) {
        const history = await fetchLoanPayments(pastPaymentLoan.id);
        setLoanPaymentsHistory(history);
        const freshLoans = await fetchLoans();
        const updated = freshLoans.find((l) => l.id === pastPaymentLoan.id);
        if (updated) setShowLoanDetail(updated);
      }
    } catch (err) {
      setFormError(err.message || 'Failed to record past payment');
    } finally {
      setFormSubmitting(false);
    }
  };

  // Borrower handlers
  const handleCreateBorrower = async (e) => {
    e.preventDefault();
    setFormError(null);
    setFormSubmitting(true);
    try {
      const createdBorrower = await createBorrower({ ...borrowerForm, phone: borrowerForm.phone || undefined });
      setBorrowerForm({ name: '', email: '', phone: '', password: '' });
      setShowBorrowerModal(false);
      if (createdBorrower.email_delivery_status === 'SENT') {
        flash('Borrower created and welcome email sent successfully.');
      } else {
        flash('Borrower created successfully.');
        setError(
          `Welcome email was not sent: ${
            createdBorrower.email_delivery_error || 'email delivery was skipped. Check SMTP configuration.'
          }`
        );
      }
      await loadBorrowers();
      await loadStats();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setFormSubmitting(false);
    }
  };

  const [dispatchingReminders, setDispatchingReminders] = useState(false);

  const handleToggleActive = async (b) => {
    try {
      if (b.is_active) await deactivateBorrower(b.id);
      else await updateBorrower(b.id, { is_active: true });
      await loadBorrowers();
      await loadStats();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleToggleReminder = async (b) => {
    try {
      const nextState = !b.monthly_reminder_enabled;
      await toggleBorrowerReminder(b.id, nextState);
      flash(`Monthly email reminders ${nextState ? 'enabled' : 'disabled'} for ${b.name}.`);
      await loadBorrowers();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDeleteBorrower = async (b) => {
    if (
      !window.confirm(
        `Are you sure you want to permanently delete borrower "${b.name}"?\n\nThis will permanently delete the borrower and all associated loans and payment records.`
      )
    ) {
      return;
    }
    try {
      await deleteBorrower(b.id);
      flash(`Borrower "${b.name}" and all associated records deleted successfully.`);
      if (viewingBorrower && viewingBorrower.id === b.id) {
        setViewingBorrower(null);
      }
      await loadBorrowers();
      await loadLoans();
      await loadPayments();
      await loadStats();
    } catch (err) {
      setError(err.message || 'Failed to delete borrower.');
    }
  };

  const handleDeleteLoan = async (l) => {
    if (
      !window.confirm(
        `Are you sure you want to permanently delete Loan #${l.id}?\n\nThis will delete the loan and all associated payment verification records.`
      )
    ) {
      return;
    }
    try {
      await deleteLoan(l.id);
      flash(`Loan #${l.id} deleted successfully.`);
      if (showLoanDetail && showLoanDetail.id === l.id) {
        setShowLoanDetail(null);
      }
      await loadLoans();
      await loadPayments();
      await loadStats();
    } catch (err) {
      setError(err.message || 'Failed to delete loan.');
    }
  };

  const handleDispatchReminders = async () => {
    setDispatchingReminders(true);
    try {
      const res = await triggerMonthlyReminders();
      flash(
        `Monthly reminders executed for ${res.target_month}: ${res.sent} sent, ${res.skipped} skipped, ${res.failed} failed.`
      );
      if (res.failed > 0) {
        const firstFailure = res.details?.find((item) => item.status === 'FAILED');
        setError(firstFailure?.error || 'One or more reminder emails could not be delivered. Check the SMTP configuration.');
      }
    } catch (err) {
      setError(err.message || 'Failed to dispatch monthly reminders.');
    } finally {
      setDispatchingReminders(false);
    }
  };


  // Loan handlers
  const handleCreateLoan = async (e) => {
    e.preventDefault();
    setFormError(null);
    setFormSubmitting(true);
    try {
      await createLoan({
        borrower_id: Number(loanForm.borrower_id),
        loan_amount: Number(loanForm.loan_amount),
        loan_date: loanForm.loan_date,
        total_payable: Number(loanForm.total_payable),
        minimum_monthly_payment: Number(loanForm.minimum_monthly_payment),
        notes: loanForm.notes || undefined,
      });
      setLoanForm({
        borrower_id: '',
        loan_amount: '',
        loan_date: '',
        total_payable: '',
        minimum_monthly_payment: '',
        notes: '',
      });
      setShowLoanModal(false);
      flash('Loan created successfully.');
      await loadLoans();
      await loadStats();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setFormSubmitting(false);
    }
  };

  const openEditLoan = (loan) => {
    setEditingLoan(loan);
    setEditLoanForm({
      loan_amount: loan.loan_amount,
      loan_date: loan.loan_date,
      total_payable: loan.total_payable,
      minimum_monthly_payment: loan.minimum_monthly_payment,
      notes: loan.notes || '',
      status: loan.status,
    });
    setFormError(null);
  };

  const handleUpdateLoan = async (e) => {
    e.preventDefault();
    setFormError(null);
    setFormSubmitting(true);
    try {
      const payload = {};
      if (editLoanForm.loan_amount !== editingLoan.loan_amount)
        payload.loan_amount = Number(editLoanForm.loan_amount);
      if (editLoanForm.loan_date !== editingLoan.loan_date)
        payload.loan_date = editLoanForm.loan_date;
      if (editLoanForm.total_payable !== editingLoan.total_payable)
        payload.total_payable = Number(editLoanForm.total_payable);
      if (editLoanForm.minimum_monthly_payment !== editingLoan.minimum_monthly_payment)
        payload.minimum_monthly_payment = Number(editLoanForm.minimum_monthly_payment);
      if (editLoanForm.notes !== (editingLoan.notes || ''))
        payload.notes = editLoanForm.notes;
      if (editLoanForm.status !== editingLoan.status)
        payload.status = editLoanForm.status;

      await updateLoan(editingLoan.id, payload);
      setEditingLoan(null);
      flash('Loan updated successfully.');
      await loadLoans();
      await loadStats();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setFormSubmitting(false);
    }
  };

  // Payment Verification Handlers
  const handleApprovePayment = async () => {
    if (!approvingPayment) return;
    setFormSubmitting(true);
    setFormError(null);
    try {
      const res = await approvePayment(approvingPayment.id);
      setApprovingPayment(null);
      if (reviewingPayment?.id === approvingPayment.id) {
        setReviewingPayment(null);
      }
      flash(res.message || `Payment #${approvingPayment.id} approved successfully.`);
      await loadPayments();
      await loadLoans();
      await loadStats();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleRejectPayment = async (e) => {
    e.preventDefault();
    if (!rejectingPayment) return;
    if (!rejectionReason.trim()) {
      setFormError('Please state a reason for rejecting this payment.');
      return;
    }
    setFormSubmitting(true);
    setFormError(null);
    try {
      await rejectPayment(rejectingPayment.id, rejectionReason.trim());
      setRejectingPayment(null);
      setRejectionReason('');
      if (reviewingPayment?.id === rejectingPayment.id) {
        setReviewingPayment(null);
      }
      flash(`Payment #${rejectingPayment.id} rejected.`);
      await loadPayments();
      await loadLoans();
      await loadStats();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setFormSubmitting(false);
    }
  };

  const activeBorrowers = borrowers.filter((b) => b.is_active);
  const filteredBorrowers = borrowers.filter((borrower) => {
    const search = borrowerSearch.trim().toLowerCase();
    const matchesSearch = !search || [borrower.name, borrower.email, borrower.phone]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(search));
    const remindersEnabled = borrower.monthly_reminder_enabled !== false;
    const matchesFilter =
      borrowerFilter === 'ALL' ||
      (borrowerFilter === 'ACTIVE' && borrower.is_active) ||
      (borrowerFilter === 'INACTIVE' && !borrower.is_active) ||
      (borrowerFilter === 'REMINDERS_ON' && remindersEnabled) ||
      (borrowerFilter === 'REMINDERS_OFF' && !remindersEnabled);
    return matchesSearch && matchesFilter;
  });
  const filteredLoans = loans.filter(
    (loan) => loanBorrowerFilter === 'ALL' || String(loan.borrower_id) === loanBorrowerFilter
  );
  const sortedLoans = sortLoans(filteredLoans, loanSort);

  // Filtered payments for Payments tab
  const displayedPayments =
    paymentFilter === 'ALL'
      ? allPayments
      : allPayments.filter((p) => p.status === paymentFilter);

  // Paginated slices with bounds-safe clamping
  const safeBorrowersPage = Math.min(
    borrowersPage,
    Math.max(1, Math.ceil(filteredBorrowers.length / borrowersPerPage))
  );
  const paginatedBorrowers = filteredBorrowers.slice(
    (safeBorrowersPage - 1) * borrowersPerPage,
    safeBorrowersPage * borrowersPerPage
  );

  const safeLoansPage = Math.min(
    loansPage,
    Math.max(1, Math.ceil(sortedLoans.length / loansPerPage))
  );
  const paginatedLoans = sortedLoans.slice(
    (safeLoansPage - 1) * loansPerPage,
    safeLoansPage * loansPerPage
  );

  const safePaymentsPage = Math.min(
    paymentsPage,
    Math.max(1, Math.ceil(displayedPayments.length / paymentsPerPage))
  );
  const paginatedPayments = displayedPayments.slice(
    (safePaymentsPage - 1) * paymentsPerPage,
    safePaymentsPage * paymentsPerPage
  );

  return (
    <div className="dashboard-page">
      {/* ── Page Hero Header ──────────────────────────────────────── */}
      <header className="dashboard-hero">
        <div className="dashboard-role-tag">KredoBook Administration</div>
        <h1 className="dashboard-title">
          {activeTab === 'dashboard' && 'KredoBook Dashboard'}
          {activeTab === 'borrowers' && 'Borrower Accounts'}
          {activeTab === 'loans' && 'Loan Management'}
          {activeTab === 'payments' && 'Payment Verification'}
        </h1>
        <p className="dashboard-welcome">
          Logged in as <strong>{currentUser?.name}</strong> •{' '}
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
          <button className="btn-sm btn-ghost" onClick={() => setError(null)}>
            Dismiss
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
          className={`tab-btn ${activeTab === 'borrowers' ? 'active' : ''}`}
          onClick={() => switchTab('borrowers')}
        >
          Borrowers ({borrowers.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'loans' ? 'active' : ''}`}
          onClick={() => switchTab('loans')}
        >
          Loans ({loans.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'payments' ? 'active' : ''}`}
          onClick={() => switchTab('payments')}
        >
          Payments
          {pendingPayments.length > 0 && (
            <span className="tab-badge">{pendingPayments.length}</span>
          )}
        </button>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          VIEW 1: ADMIN DASHBOARD OVERVIEW
      ═══════════════════════════════════════════════════════════════ */}
      {activeTab === 'dashboard' && (
        <div className="dashboard-overview-container">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#f8fafc', margin: 0 }}>Portfolio Overview</h2>
              <p style={{ color: '#94a3b8', fontSize: '0.85rem', margin: '2px 0 0' }}>Real-time overview of active borrowers, balances, and repayments</p>
            </div>
            <button
              type="button"
              className="btn-sm btn-outline"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '8px 14px', borderRadius: '8px' }}
              onClick={handleDispatchReminders}
              disabled={dispatchingReminders}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 16, height: 16 }}>
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
              <span>{dispatchingReminders ? 'Sending Reminders...' : 'Trigger Monthly Reminders'}</span>
            </button>
          </div>

          {/* Summary KPI Cards */}
          <section className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon-wrap icon-indigo">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="stat-icon">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
              <div className="stat-content">
                <span className="stat-label">Total Borrowers</span>
                <span className="stat-value">{stats ? stats.total_borrowers : statsLoading ? '—' : 0}</span>
                <span className="stat-hint">{activeBorrowers.length} active accounts</span>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon-wrap icon-cyan">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="stat-icon">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
              </div>
              <div className="stat-content">
                <span className="stat-label">Active Loans</span>
                <span className="stat-value">{stats ? stats.active_loans : statsLoading ? '—' : 0}</span>
                <span className="stat-hint">{loans.length} total loans issued</span>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon-wrap icon-green">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="stat-icon">
                  <line x1="12" y1="1" x2="12" y2="23" />
                  <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                </svg>
              </div>
              <div className="stat-content">
                <span className="stat-label">Total Amount Lent</span>
                <span className="stat-value">
                  {stats ? formatCurrency(stats.total_amount_lent) : statsLoading ? '—' : '₹0.00'}
                </span>
                <span className="stat-hint">Active + Paid principal</span>
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
                  {stats ? formatCurrency(stats.total_outstanding) : statsLoading ? '—' : '₹0.00'}
                </span>
                <span className="stat-hint">Portfolio balance remaining</span>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon-wrap" style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5' }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="stat-icon">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <line x1="12" y1="18" x2="12" y2="12" />
                  <line x1="12" y1="9" x2="12.01" y2="9" />
                </svg>
              </div>
              <div className="stat-content">
                <span className="stat-label">Pending Payments</span>
                <span className="stat-value" style={{ color: pendingPayments.length > 0 ? '#fca5a5' : '#fff' }}>
                  {pendingPayments.length}
                </span>
                <span className="stat-hint">
                  {pendingPayments.length > 0 ? 'Requires action' : 'All caught up'}
                </span>
              </div>
            </div>
          </section>

          {/* Pending Payments Action Widget */}
          {pendingPayments.length > 0 && (
            <section className="dashboard-section card" style={{ borderColor: 'rgba(245, 158, 11, 0.3)' }}>
              <div className="card-top-bar">
                <div>
                  <span className="section-eyebrow" style={{ color: '#fcd34d' }}>Action Required</span>
                  <h2 className="section-title">Pending Repayments Awaiting Review ({pendingPayments.length})</h2>
                  <p className="section-desc">Borrowers submitted payments with proof that must be manually verified</p>
                </div>
                <button className="btn-sm btn-outline" onClick={() => switchTab('payments')}>
                  Open Verification Hub →
                </button>
              </div>

              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Payment ID</th>
                      <th>Borrower</th>
                      <th>Loan ID</th>
                      <th>Amount</th>
                      <th>Month</th>
                      <th>Payment Date</th>
                      <th>Submitted At</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingPayments.slice(0, 5).map((p) => (
                      <tr key={p.id}>
                        <td className="font-mono text-bold">#{p.id}</td>
                        <td className="text-bold">{p.borrower?.name || `Borrower #${p.borrower_id}`}</td>
                        <td className="font-mono">Loan #{p.loan_id}</td>
                        <td className="font-mono text-bold text-success">{formatCurrency(p.amount)}</td>
                        <td className="font-mono">{p.payment_month}</td>
                        <td>{formatDate(p.payment_date)}</td>
                        <td className="text-muted">{new Date(p.submitted_at).toLocaleDateString()}</td>
                        <td>
                          <button
                            className="btn-sm btn-outline"
                            onClick={() => {
                              switchTab('payments');
                              setReviewingPayment(p);
                            }}
                          >
                            Review Proof
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Recent Loans Overview */}
          <section className="dashboard-section card">
            <div className="card-top-bar">
              <div>
                <span className="section-eyebrow">Recent Activity</span>
                <h2 className="section-title">Active Loans Portfolio</h2>
                <p className="section-desc">Snapshot of active borrower accounts and current balances</p>
              </div>
              <button className="btn-sm btn-ghost" onClick={() => switchTab('loans')}>
                View All Loans ({loans.length}) →
              </button>
            </div>

            {loansLoading ? (
              <div className="loading-state">
                <div className="spinner" />
                <p>Loading loans snapshot...</p>
              </div>
            ) : loans.length === 0 ? (
              <div className="empty-state">
                <h3>No loans issued yet</h3>
                <p>Click "Loans" in the top bar to create a new borrower loan.</p>
              </div>
            ) : (
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Loan ID</th>
                      <th>Borrower</th>
                      <th>Loan Date</th>
                      <th>Principal</th>
                      <th>Total Payable</th>
                      <th>Verified Paid</th>
                      <th>Outstanding</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loans.slice(0, 5).map((l) => (
                      <tr key={l.id}>
                        <td className="font-mono text-bold">#{l.id}</td>
                        <td className="cell-name">{l.borrower?.name}</td>
                        <td className="cell-date">{formatDate(l.loan_date)}</td>
                        <td className="font-mono">{formatCurrency(l.loan_amount)}</td>
                        <td className="font-mono">{formatCurrency(l.total_payable)}</td>
                        <td className="font-mono text-success">{formatCurrency(l.total_paid)}</td>
                        <td className="font-mono text-bold text-highlight">
                          {formatCurrency(l.remaining_balance)}
                        </td>
                        <td>
                          <span
                            className={`status-pill ${
                              l.status === 'ACTIVE'
                                ? 'pill-active'
                                : l.status === 'PAID'
                                ? 'pill-paid'
                                : 'pill-inactive'
                            }`}
                          >
                            {l.status}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <button className="btn-sm btn-outline" onClick={() => openLoanDetail(l)}>
                              View
                            </button>
                            {l.status !== 'PAID' && l.status !== 'CANCELLED' && (
                              <button
                                className="btn-sm"
                                style={{
                                  background: 'rgba(16, 185, 129, 0.15)',
                                  color: '#6ee7b7',
                                  border: '1px solid rgba(16, 185, 129, 0.3)',
                                  padding: '3px 8px',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '0.78rem',
                                  fontWeight: '600',
                                }}
                                onClick={() => openRecordPastPayment(l)}
                                title="Record past/offline payment"
                              >
                                + Pay
                              </button>
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
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          VIEW 2: BORROWERS PAGE
      ═══════════════════════════════════════════════════════════════ */}
      {activeTab === 'borrowers' && (
        <section className="dashboard-section card">
          <div className="card-top-bar">
            <div>
              <span className="section-eyebrow">User Management</span>
              <h2 className="section-title">All Registered Borrowers ({borrowers.length})</h2>
              <p className="section-desc">Create borrowers, manage credentials, and inspect account portfolios</p>
            </div>
            <button
              onClick={() => {
                setFormError(null);
                setShowBorrowerModal(true);
              }}
              className="primary-action-btn"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="9" cy="8" r="3" />
                <path d="M3.5 20a5.5 5.5 0 0 1 11 0" />
                <path d="M18 8v6M15 11h6" />
              </svg>
              <span>Add Borrower</span>
            </button>
          </div>

          {borrowersLoading ? (
            <div className="loading-state">
              <div className="spinner" />
              <p>Loading borrowers...</p>
            </div>
          ) : borrowers.length === 0 ? (
            <div className="empty-state">
              <h3>No borrowers registered</h3>
              <p>Click "Add Borrower" to register a borrower account.</p>
            </div>
          ) : (
            <>
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Phone</th>
                      <th>Account Status</th>
                      <th>Email Reminders</th>
                      <th>Created At</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedBorrowers.map((b) => (
                      <tr key={b.id} className={!b.is_active ? 'row-inactive' : ''}>
                        <td className="font-mono text-bold">#{b.id}</td>
                        <td className="cell-name">{b.name}</td>
                        <td className="cell-email">{b.email}</td>
                        <td>{b.phone || '—'}</td>
                        <td>
                          <span className={`status-pill ${b.is_active ? 'pill-active' : 'pill-inactive'}`}>
                            {b.is_active ? 'Active' : 'Deactivated'}
                          </span>
                        </td>
                        <td>
                          <button
                            type="button"
                            onClick={() => handleToggleReminder(b)}
                            className={`status-pill ${b.monthly_reminder_enabled !== false ? 'pill-paid' : 'pill-inactive'}`}
                            style={{ cursor: 'pointer', border: 'none', padding: '4px 10px' }}
                            title="Click to toggle monthly payment reminder setting"
                          >
                            {b.monthly_reminder_enabled !== false ? '✓ Enabled' : '✕ Disabled'}
                          </button>
                        </td>
                        <td className="cell-date">{formatDate(b.created_at)}</td>
                        <td>
                          <div className="table-actions">
                            <button className="btn-sm btn-outline" onClick={() => openBorrowerDetail(b)}>
                              View Loans
                            </button>
                            <button
                              onClick={() => handleToggleActive(b)}
                              className={`action-btn-sm ${b.is_active ? 'btn-deactivate' : 'btn-activate'}`}
                            >
                              {b.is_active ? 'Deactivate' : 'Activate'}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteBorrower(b)}
                              className="btn-sm action-delete"
                              title="Permanently delete borrower"
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <MinimalPagination
                currentPage={safeBorrowersPage}
                totalItems={borrowers.length}
                pageSize={borrowersPerPage}
                onPageChange={setBorrowersPage}
                itemLabel="borrowers"
              />
            </>
          )}
        </section>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          VIEW 3: LOANS PAGE
      ═══════════════════════════════════════════════════════════════ */}
      {activeTab === 'loans' && (
        <section className="dashboard-section card">
          <div className="card-top-bar">
            <div>
              <span className="section-eyebrow">Loan Management</span>
              <h2 className="section-title">All Loans ({filteredLoans.length})</h2>
              <p className="section-desc">Issue loans, inspect balances, and edit repayment terms</p>
            </div>
            <button
              onClick={() => {
                setFormError(null);
                setShowLoanModal(true);
              }}
              className="primary-action-btn"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="4" width="12" height="9" rx="2" />
                <path d="M7 17h10a2 2 0 0 0 2-2v-7" />
                <path d="M18 5v6M15 8h6" />
              </svg>
              <span>Create Loan</span>
            </button>
          </div>

          <div className="loan-toolbar" aria-label="Loan list controls">
            <label>
              <span>Borrower</span>
              <select
                className="form-input"
                value={loanBorrowerFilter}
                onChange={(event) => {
                  setLoanBorrowerFilter(event.target.value);
                  setLoansPage(1);
                }}
              >
                <option value="ALL">All borrowers</option>
                {borrowers.map((borrower) => (
                  <option key={borrower.id} value={String(borrower.id)}>
                    {borrower.name} ({borrower.email})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Sort loans</span>
              <select
                className="form-input"
                value={loanSort}
                onChange={(event) => {
                  setLoanSort(event.target.value);
                  setLoansPage(1);
                }}
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="largest">Highest amount</option>
                <option value="smallest">Lowest amount</option>
              </select>
            </label>
          </div>

          {loansLoading ? (
            <div className="loading-state">
              <div className="spinner" />
              <p>Loading loan records...</p>
            </div>
          ) : filteredLoans.length === 0 ? (
            <div className="empty-state">
              <h3>{loans.length === 0 ? 'No loans issued yet' : 'No loans match this borrower'}</h3>
              <p>
                {loans.length === 0
                  ? 'Click "Create Loan" to assign a new loan to an active borrower.'
                  : 'Choose another borrower or select all borrowers to view more loans.'}
              </p>
            </div>
          ) : (
            <>
              <div className="table-responsive loan-table">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '45px' }}>#</th>
                      <th>Borrower</th>
                      <th>Date</th>
                      <th>Principal</th>
                      <th>Total</th>
                      <th>Paid</th>
                      <th>Remaining</th>
                      <th>Min/Mo</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedLoans.map((l) => (
                      <tr key={l.id} className={l.status === 'CANCELLED' ? 'row-inactive' : ''}>
                        <td className="font-mono text-bold cell-id">#{l.id}</td>
                        <td>
                          <div className="cell-name">{l.borrower?.name}</div>
                          <div className="cell-email">{l.borrower?.email}</div>
                        </td>
                        <td className="cell-date">{formatDate(l.loan_date)}</td>
                        <td className="font-mono">{formatCurrency(l.loan_amount)}</td>
                        <td className="font-mono">{formatCurrency(l.total_payable)}</td>
                        <td className="font-mono text-success">{formatCurrency(l.total_paid)}</td>
                        <td className="font-mono text-bold text-highlight">
                          {formatCurrency(l.remaining_balance)}
                        </td>
                        <td className="font-mono text-muted">{formatCurrency(l.minimum_monthly_payment)}</td>
                        <td>
                          <span
                            className={`status-pill ${
                              l.status === 'ACTIVE'
                                ? 'pill-active'
                                : l.status === 'PAID'
                                ? 'pill-paid'
                                : 'pill-inactive'
                            }`}
                          >
                            {l.status}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <div className="table-actions loan-actions">
                            <button className="btn-sm btn-outline action-icon-btn" onClick={() => openLoanDetail(l)} title="View loan details" aria-label="View loan details">
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z"/><circle cx="12" cy="12" r="2.5"/></svg>
                            </button>
                            {l.status !== 'PAID' && l.status !== 'CANCELLED' && (
                              <button
                                type="button"
                                className="btn-sm btn-success-action action-icon-btn"
                                onClick={() => openRecordPastPayment(l)}
                                title="Record past/offline payment"
                                aria-label="Record payment"
                              >
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 7h16v10H4z"/><path d="M16 12h.01M8 11h4M10 9v4"/></svg>
                              </button>
                            )}
                            <button className="btn-sm btn-ghost action-icon-btn" onClick={() => openEditLoan(l)} title="Edit loan" aria-label="Edit loan">
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/></svg>
                            </button>
                            <button
                              type="button"
                              className="btn-sm btn-danger-action action-icon-btn"
                              onClick={() => handleDeleteLoan(l)}
                              title="Permanently delete loan"
                              aria-label="Delete loan"
                            >
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 7h16M10 11v6M14 11v6M9 7l1-3h4l1 3M6 7l1 13h10l1-13"/></svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <MinimalPagination
                currentPage={safeLoansPage}
                totalItems={filteredLoans.length}
                pageSize={loansPerPage}
                onPageChange={setLoansPage}
                itemLabel="loans"
              />
            </>
          )}
        </section>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          VIEW 4: PAYMENTS PAGE (CENTRAL VERIFICATION AREA)
      ═══════════════════════════════════════════════════════════════ */}
      {activeTab === 'payments' && (
        <section className="dashboard-section card">
          <div className="card-top-bar">
            <div>
              <span className="section-eyebrow">Payment Verification & Audit</span>
              <h2 className="section-title">Payment Submissions ({allPayments.length})</h2>
              <p className="section-desc">Review payment screenshots, approve verified transfers, and manage rejected proofs</p>
            </div>
            <button className="btn-sm btn-ghost" onClick={loadPayments} disabled={paymentsLoading}>
              {paymentsLoading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          {/* Status Filter Tabs */}
          <div className="filter-button-bar" style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
            <button
              className={`btn-sm ${paymentFilter === 'PENDING' ? 'btn-outline active-filter' : 'btn-ghost'}`}
              onClick={() => setPaymentFilter('PENDING')}
            >
              Pending ({allPayments.filter((p) => p.status === 'PENDING').length})
            </button>
            <button
              className={`btn-sm ${paymentFilter === 'VERIFIED' ? 'btn-outline active-filter' : 'btn-ghost'}`}
              onClick={() => setPaymentFilter('VERIFIED')}
            >
              Verified ({allPayments.filter((p) => p.status === 'VERIFIED').length})
            </button>
            <button
              className={`btn-sm ${paymentFilter === 'REJECTED' ? 'btn-outline active-filter' : 'btn-ghost'}`}
              onClick={() => setPaymentFilter('REJECTED')}
            >
              Rejected ({allPayments.filter((p) => p.status === 'REJECTED').length})
            </button>
            <button
              className={`btn-sm ${paymentFilter === 'ALL' ? 'btn-outline active-filter' : 'btn-ghost'}`}
              onClick={() => setPaymentFilter('ALL')}
            >
              All Records ({allPayments.length})
            </button>
          </div>

          {paymentsLoading ? (
            <div className="loading-state">
              <div className="spinner" />
              <p>Loading payments data...</p>
            </div>
          ) : displayedPayments.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              </div>
              <h3>No payments in this category</h3>
              <p>No payments match the "{paymentFilter}" status filter.</p>
            </div>
          ) : (
            <>
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Payment ID</th>
                      <th>Borrower</th>
                      <th>Loan ID</th>
                      <th>Amount Paid</th>
                      <th>Month</th>
                      <th>Payment Date</th>
                      <th>Submitted At</th>
                      <th>Status</th>
                      <th>Verification Details / Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedPayments.map((p) => (
                      <tr key={p.id}>
                        <td className="font-mono text-bold">#{p.id}</td>
                        <td>
                          <div className="text-bold">{p.borrower?.name || `Borrower #${p.borrower_id}`}</div>
                          <div className="text-muted" style={{ fontSize: '0.8rem' }}>{p.borrower?.email}</div>
                        </td>
                        <td className="font-mono">
                          <span className="badge-outline">Loan #{p.loan_id}</span>
                        </td>
                        <td className="font-mono text-bold text-success" style={{ fontSize: '1.05rem' }}>
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
                              onClick={() => setReviewingPayment(p)}
                              title="Inspect screenshot proof"
                            >
                              Review Proof
                            </button>

                            {p.status === 'PENDING' && (
                              <>
                                <button
                                  className="btn-sm btn-success-action"
                                  onClick={() => {
                                    setFormError(null);
                                    setApprovingPayment(p);
                                  }}
                                >
                                  Approve
                                </button>
                                <button
                                  className="btn-sm btn-danger-action"
                                  onClick={() => {
                                    setFormError(null);
                                    setRejectionReason('');
                                    setRejectingPayment(p);
                                  }}
                                >
                                  Reject
                                </button>
                              </>
                            )}

                            {p.status === 'VERIFIED' && (
                              <>
                                <span className="text-muted" style={{ fontSize: '0.8rem' }}>
                                  Verified {p.verified_at ? formatDate(p.verified_at) : ''}
                                </span>
                                {!p.screenshot_url && (
                                  <button
                                    className="btn-sm btn-outline"
                                    onClick={() => openEditPastPayment(p)}
                                    title="Correct this past/offline payment"
                                  >
                                    Edit Past Payment
                                  </button>
                                )}
                              </>
                            )}

                            {p.status === 'REJECTED' && p.rejection_reason && (
                              <div className="rejection-reason-chip" title={p.rejection_reason}>
                                <span style={{ color: '#fca5a5' }}>{p.rejection_reason}</span>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <MinimalPagination
                currentPage={safePaymentsPage}
                totalItems={displayedPayments.length}
                pageSize={paymentsPerPage}
                onPageChange={setPaymentsPage}
                itemLabel="payments"
              />
            </>
          )}
        </section>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          MODALS
      ═══════════════════════════════════════════════════════════════ */}

      {/* ── MODAL: Borrower Profile & Assigned Loans ──────────────── */}
      {viewingBorrower && (
        <div className="modal-backdrop" onClick={() => setViewingBorrower(null)}>
          <div className="modal-card modal-lg" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="section-eyebrow">Borrower Profile</span>
                <h3 className="modal-title">{viewingBorrower.name}</h3>
              </div>
              <button className="modal-close" onClick={() => setViewingBorrower(null)}>
                ×
              </button>
            </div>

            <div className="modal-body">
              <div className="profile-details-grid" style={{ marginBottom: '24px' }}>
                <div className="profile-field">
                  <span className="field-label">Email</span>
                  <span className="field-value">{viewingBorrower.email}</span>
                </div>
                <div className="profile-field">
                  <span className="field-label">Phone</span>
                  <span className="field-value">{viewingBorrower.phone || 'Not provided'}</span>
                </div>
                <div className="profile-field">
                  <span className="field-label">Account Status</span>
                  <span className="field-value">
                    <span className={`status-pill ${viewingBorrower.is_active ? 'pill-active' : 'pill-inactive'}`}>
                      {viewingBorrower.is_active ? 'Active' : 'Deactivated'}
                    </span>
                  </span>
                </div>
                <div className="profile-field">
                  <span className="field-label">Member Since</span>
                  <span className="field-value">{formatDate(viewingBorrower.created_at)}</span>
                </div>
              </div>

              <h4 style={{ color: '#fff', marginBottom: '12px' }}>
                Assigned Loans ({borrowerLoans.length})
              </h4>
              {borrowerLoans.length === 0 ? (
                <p className="text-muted" style={{ fontSize: '0.9rem' }}>
                  No loans currently assigned to this borrower.
                </p>
              ) : (
                <div className="table-responsive">
                  <table className="data-table" style={{ fontSize: '0.85rem' }}>
                    <thead>
                      <tr>
                        <th>Loan ID</th>
                        <th>Loan Date</th>
                        <th>Principal</th>
                        <th>Total Payable</th>
                        <th>Paid</th>
                        <th>Remaining</th>
                        <th>Status</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {borrowerLoans.map((l) => (
                        <tr key={l.id}>
                          <td className="font-mono text-bold">#{l.id}</td>
                          <td className="cell-date">{formatDate(l.loan_date)}</td>
                          <td className="font-mono">{formatCurrency(l.loan_amount)}</td>
                          <td className="font-mono">{formatCurrency(l.total_payable)}</td>
                          <td className="font-mono text-success">{formatCurrency(l.total_paid)}</td>
                          <td className="font-mono text-bold text-highlight">{formatCurrency(l.remaining_balance)}</td>
                          <td>
                            <span
                              className={`status-pill ${
                                l.status === 'ACTIVE'
                                  ? 'pill-active'
                                  : l.status === 'PAID'
                                  ? 'pill-paid'
                                  : 'pill-inactive'
                              }`}
                            >
                              {l.status}
                            </span>
                          </td>
                          <td>
                            <button
                              className="btn-sm btn-outline"
                              onClick={() => {
                                setViewingBorrower(null);
                                openLoanDetail(l);
                              }}
                            >
                              Details
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setViewingBorrower(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Review Screenshot & Proof ───────────────────────── */}
      {reviewingPayment && (
        <div className="modal-backdrop" onClick={() => setReviewingPayment(null)}>
          <div className="modal-card modal-lg" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="section-eyebrow">Payment Verification</span>
                <h3 className="modal-title">Payment Proof #{reviewingPayment.id}</h3>
              </div>
              <button className="modal-close" onClick={() => setReviewingPayment(null)}>
                ×
              </button>
            </div>

            <div className="modal-body">
              <div className="loan-detail-highlight-grid">
                <div className="highlight-box">
                  <span className="hl-label">Payment Amount</span>
                  <span className="hl-value text-success">{formatCurrency(reviewingPayment.amount)}</span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Target Loan</span>
                  <span className="hl-value">Loan #{reviewingPayment.loan_id}</span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Borrower</span>
                  <span className="hl-value" style={{ fontSize: '1.1rem' }}>
                    {reviewingPayment.borrower?.name || `Borrower #${reviewingPayment.borrower_id}`}
                  </span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Payment Month & Date</span>
                  <span className="hl-value" style={{ fontSize: '1.1rem' }}>
                    {reviewingPayment.payment_month} • {formatDate(reviewingPayment.payment_date)}
                  </span>
                </div>
              </div>

              {reviewingPayment.rejection_reason && (
                <div className="alert-banner alert-error" style={{ marginBottom: '16px' }}>
                  <strong>Rejection Note:</strong> {reviewingPayment.rejection_reason}
                </div>
              )}

              {/* Screenshot Preview */}
              <div className="screenshot-preview-container">
                <div className="screenshot-preview-header">
                  <span className="screenshot-title">Uploaded Payment Screenshot</span>
                </div>
                {screenshotLoading ? (
                  <div className="loading-state">
                    <div className="spinner" />
                    <p>Fetching secured screenshot proof...</p>
                  </div>
                ) : screenshotError ? (
                  <div className="alert-banner alert-error">
                    <span>{screenshotError}</span>
                  </div>
                ) : screenshotUrl ? (
                  <div className="screenshot-img-wrapper">
                    <img
                      src={screenshotUrl}
                      alt={`Payment ${reviewingPayment.id} Screenshot`}
                      className="screenshot-img"
                    />
                  </div>
                ) : null}
              </div>
            </div>

            <div className="modal-footer">
              {reviewingPayment.status === 'PENDING' && (
                <>
                  <button
                    className="btn-danger-action"
                    onClick={() => {
                      setFormError(null);
                      setRejectionReason('');
                      setRejectingPayment(reviewingPayment);
                    }}
                  >
                    Reject Payment
                  </button>
                  <button
                    className="btn-success-action"
                    onClick={() => {
                      setFormError(null);
                      setApprovingPayment(reviewingPayment);
                    }}
                  >
                    Approve Payment
                  </button>
                </>
              )}
              <button className="btn-secondary" onClick={() => setReviewingPayment(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Approve Confirmation ───────────────────────────── */}
      {approvingPayment && (
        <div className="modal-backdrop" onClick={() => !formSubmitting && setApprovingPayment(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Confirm Payment Approval</h3>
              <button className="modal-close" onClick={() => setApprovingPayment(null)}>
                ×
              </button>
            </div>

            <div className="modal-body">
              {formError && (
                <div className="alert-banner alert-error" style={{ marginBottom: '16px' }}>
                  <span>{formError}</span>
                </div>
              )}
              <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>
                Are you sure you want to approve this payment? This will mark the payment as{' '}
                <strong style={{ color: '#6ee7b7' }}>VERIFIED</strong> and immediately deduct the amount from
                the loan's outstanding balance.
              </p>

              <div className="highlight-box" style={{ marginBottom: '16px' }}>
                <div className="meta-item" style={{ marginBottom: '8px' }}>
                  <span className="meta-label">Payment ID</span>
                  <span className="meta-value font-mono">#{approvingPayment.id}</span>
                </div>
                <div className="meta-item" style={{ marginBottom: '8px' }}>
                  <span className="meta-label">Payment Amount</span>
                  <span className="meta-value text-success font-mono">
                    {formatCurrency(approvingPayment.amount)}
                  </span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Target Loan</span>
                  <span className="meta-value font-mono">Loan #{approvingPayment.loan_id}</span>
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn-secondary"
                disabled={formSubmitting}
                onClick={() => setApprovingPayment(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="submit-btn"
                style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}
                disabled={formSubmitting}
                onClick={handleApprovePayment}
              >
                {formSubmitting ? 'Approving...' : 'Confirm Approval'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Reject Reason Form ──────────────────────────────── */}
      {rejectingPayment && (
        <div className="modal-backdrop" onClick={() => !formSubmitting && setRejectingPayment(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Reject Payment #{rejectingPayment.id}</h3>
              <button className="modal-close" onClick={() => setRejectingPayment(null)}>
                ×
              </button>
            </div>

            <form onSubmit={handleRejectPayment} className="modal-form">
              {formError && (
                <div className="alert-banner alert-error">
                  <span>{formError}</span>
                </div>
              )}
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                Provide a clear reason explaining why this payment proof was rejected. The borrower will see
                this explanation in their dashboard.
              </p>

              <div className="form-group">
                <label className="form-label">Rejection Reason *</label>
                <textarea
                  required
                  rows={4}
                  className="form-input"
                  placeholder="e.g. Screenshot does not clearly show transaction reference / Amount mismatch"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                />
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={formSubmitting}
                  onClick={() => setRejectingPayment(null)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="submit-btn"
                  style={{ background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)' }}
                  disabled={formSubmitting}
                >
                  {formSubmitting ? 'Rejecting...' : 'Confirm Rejection'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── MODAL: Loan Details & Payment History ─────────────────── */}
      {showLoanDetail && (
        <div className="modal-backdrop" onClick={() => setShowLoanDetail(null)}>
          <div className="modal-card modal-lg" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="section-eyebrow">Loan #{showLoanDetail.id}</span>
                <h3 className="modal-title">Loan Overview & Payment History</h3>
              </div>
              <button className="modal-close" onClick={() => setShowLoanDetail(null)}>
                ×
              </button>
            </div>

            <div className="modal-body">
              <div className="loan-detail-highlight-grid">
                <div className="highlight-box">
                  <span className="hl-label">Borrower</span>
                  <span className="hl-value" style={{ fontSize: '1.1rem' }}>
                    {showLoanDetail.borrower?.name}
                  </span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Loan Date (Money Given)</span>
                  <span className="hl-value" style={{ fontSize: '1.1rem' }}>
                    {formatDate(showLoanDetail.loan_date)}
                  </span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Original Loan Amount</span>
                  <span className="hl-value">{formatCurrency(showLoanDetail.loan_amount)}</span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Total Payable</span>
                  <span className="hl-value">{formatCurrency(showLoanDetail.total_payable)}</span>
                </div>
                <div className="highlight-box">
                  <span className="hl-label">Total Paid</span>
                  <span className="hl-value text-success">{formatCurrency(showLoanDetail.total_paid)}</span>
                </div>
                <div className="highlight-box highlight-accent">
                  <span className="hl-label">Remaining Balance</span>
                  <span className="hl-value text-highlight">
                    {formatCurrency(showLoanDetail.remaining_balance)}
                  </span>
                </div>
              </div>

              <div className="loan-meta-grid">
                <div className="meta-item">
                  <span className="meta-label">Minimum Monthly Payment</span>
                  <span className="meta-value font-mono">
                    {formatCurrency(showLoanDetail.minimum_monthly_payment)}
                  </span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Loan Status</span>
                  <span className="meta-value">
                    <span
                      className={`status-pill ${
                        showLoanDetail.status === 'ACTIVE'
                          ? 'pill-active'
                          : showLoanDetail.status === 'PAID'
                          ? 'pill-paid'
                          : 'pill-inactive'
                      }`}
                    >
                      {showLoanDetail.status}
                    </span>
                  </span>
                </div>
              </div>

              {showLoanDetail.notes && (
                <div className="loan-notes-box">
                  <span className="notes-label">Admin Notes</span>
                  <p className="notes-body">{showLoanDetail.notes}</p>
                </div>
              )}

              {/* Payment History Table for this Loan */}
              <div className="loan-payment-history-section" style={{ marginTop: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
                  <h4 style={{ color: '#fff', margin: 0 }}>Payment Submissions for this Loan</h4>
                  {showLoanDetail.status !== 'PAID' && showLoanDetail.status !== 'CANCELLED' && (
                    <button
                      type="button"
                      className="btn-sm"
                      style={{
                        background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                        color: '#fff',
                        border: 'none',
                        padding: '6px 14px',
                        borderRadius: '6px',
                        fontWeight: '600',
                        fontSize: '0.82rem',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                      onClick={() => openRecordPastPayment(showLoanDetail)}
                    >
                      + Record Past / Offline Payment
                    </button>
                  )}
                </div>
                {loanPaymentsLoading ? (
                  <div className="loading-state">
                    <div className="spinner" />
                  </div>
                ) : loanPaymentsHistory.length === 0 ? (
                  <p className="text-muted" style={{ fontSize: '0.9rem' }}>
                    No payments submitted for this loan yet.
                  </p>
                ) : (
                  <div className="table-responsive">
                    <table className="data-table" style={{ fontSize: '0.85rem' }}>
                      <thead>
                        <tr>
                          <th>Payment ID</th>
                          <th>Amount</th>
                          <th>Month</th>
                          <th>Date</th>
                          <th>Status</th>
                          <th>Details / Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {loanPaymentsHistory.map((pm) => (
                          <tr key={pm.id}>
                            <td className="font-mono text-bold">#{pm.id}</td>
                            <td className="font-mono text-bold">{formatCurrency(pm.amount)}</td>
                            <td className="font-mono">{pm.payment_month}</td>
                            <td>{formatDate(pm.payment_date)}</td>
                            <td>
                              <span
                                className={`status-pill ${
                                  pm.status === 'VERIFIED'
                                    ? 'pill-paid'
                                    : pm.status === 'PENDING'
                                    ? 'pill-amber'
                                    : 'pill-inactive'
                                }`}
                              >
                                {pm.status}
                              </span>
                            </td>
                            <td>
                              {pm.rejection_reason ? (
                                <span style={{ color: pm.status === 'VERIFIED' ? '#93c5fd' : '#fca5a5' }}>
                                  {pm.rejection_reason}
                                </span>
                              ) : pm.verified_at ? (
                                <span className="text-muted">
                                  Verified on {new Date(pm.verified_at).toLocaleDateString()}
                                </span>
                              ) : (
                                <span className="text-muted">Awaiting review</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowLoanDetail(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Create Loan ────────────────────────────────────── */}
      {showLoanModal && (
        <div className="modal-backdrop" onClick={() => setShowLoanModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Create New Loan</h3>
              <button className="modal-close" onClick={() => setShowLoanModal(false)}>
                ×
              </button>
            </div>
            {formError && (
              <div className="alert-banner alert-error" style={{ marginBottom: '16px' }}>
                <span>{formError}</span>
              </div>
            )}
            <form onSubmit={handleCreateLoan} className="modal-form">
              <div className="form-group">
                <label className="form-label">Borrower *</label>
                <select
                  required
                  className="form-input"
                  value={loanForm.borrower_id}
                  onChange={(e) => setLoanForm({ ...loanForm, borrower_id: e.target.value })}
                >
                  <option value="">Select an active borrower...</option>
                  {activeBorrowers.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name} ({b.email})
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Loan Amount (₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    className="form-input"
                    value={loanForm.loan_amount}
                    onChange={(e) => setLoanForm({ ...loanForm, loan_amount: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Loan Date (Money Given) *</label>
                  <input
                    type="date"
                    required
                    className="form-input"
                    value={loanForm.loan_date}
                    onChange={(e) => setLoanForm({ ...loanForm, loan_date: e.target.value })}
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Total Payable (₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    className="form-input"
                    value={loanForm.total_payable}
                    onChange={(e) => setLoanForm({ ...loanForm, total_payable: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Min Monthly Payment (₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    className="form-input"
                    value={loanForm.minimum_monthly_payment}
                    onChange={(e) =>
                      setLoanForm({ ...loanForm, minimum_monthly_payment: e.target.value })
                    }
                  />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Notes</label>
                <textarea
                  className="form-input"
                  rows={3}
                  placeholder="Optional context about the loan..."
                  value={loanForm.notes}
                  onChange={(e) => setLoanForm({ ...loanForm, notes: e.target.value })}
                />
              </div>
              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setShowLoanModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="submit-btn" disabled={formSubmitting}>
                  {formSubmitting ? 'Creating...' : 'Create Loan'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── MODAL: Edit Loan ──────────────────────────────────────── */}
      {editingLoan && (
        <div className="modal-backdrop" onClick={() => setEditingLoan(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Edit Loan #{editingLoan.id}</h3>
              <button className="modal-close" onClick={() => setEditingLoan(null)}>
                ×
              </button>
            </div>
            {formError && (
              <div className="alert-banner alert-error" style={{ marginBottom: '16px' }}>
                <span>{formError}</span>
              </div>
            )}
            <form onSubmit={handleUpdateLoan} className="modal-form">
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Loan Amount (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    className="form-input"
                    value={editLoanForm.loan_amount}
                    onChange={(e) => setEditLoanForm({ ...editLoanForm, loan_amount: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Loan Date</label>
                  <input
                    type="date"
                    className="form-input"
                    value={editLoanForm.loan_date}
                    onChange={(e) => setEditLoanForm({ ...editLoanForm, loan_date: e.target.value })}
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Total Payable (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    className="form-input"
                    value={editLoanForm.total_payable}
                    onChange={(e) => setEditLoanForm({ ...editLoanForm, total_payable: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Min Monthly (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    className="form-input"
                    value={editLoanForm.minimum_monthly_payment}
                    onChange={(e) =>
                      setEditLoanForm({ ...editLoanForm, minimum_monthly_payment: e.target.value })
                    }
                  />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Status</label>
                <select
                  className="form-input"
                  value={editLoanForm.status}
                  onChange={(e) => setEditLoanForm({ ...editLoanForm, status: e.target.value })}
                >
                  <option value="ACTIVE">ACTIVE</option>
                  <option value="PAID">PAID</option>
                  <option value="CANCELLED">CANCELLED</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Notes</label>
                <textarea
                  className="form-input"
                  rows={3}
                  value={editLoanForm.notes}
                  onChange={(e) => setEditLoanForm({ ...editLoanForm, notes: e.target.value })}
                />
              </div>
              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setEditingLoan(null)}>
                  Cancel
                </button>
                <button type="submit" className="submit-btn" disabled={formSubmitting}>
                  {formSubmitting ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── MODAL: Create Borrower ────────────────────────────────── */}
      {showBorrowerModal && (
        <div className="modal-backdrop" onClick={() => setShowBorrowerModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Register New Borrower</h3>
              <button className="modal-close" onClick={() => setShowBorrowerModal(false)}>
                ×
              </button>
            </div>
            {formError && (
              <div className="alert-banner alert-error" style={{ marginBottom: '16px' }}>
                <span>{formError}</span>
              </div>
            )}
            <form onSubmit={handleCreateBorrower} className="modal-form">
              <div className="form-group">
                <label className="form-label">Full Name *</label>
                <input
                  type="text"
                  required
                  className="form-input"
                  value={borrowerForm.name}
                  onChange={(e) => setBorrowerForm({ ...borrowerForm, name: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Email *</label>
                <input
                  type="email"
                  required
                  className="form-input"
                  value={borrowerForm.email}
                  onChange={(e) => setBorrowerForm({ ...borrowerForm, email: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Phone</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Optional phone number"
                  value={borrowerForm.phone}
                  onChange={(e) => setBorrowerForm({ ...borrowerForm, phone: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Password *</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  className="form-input"
                  placeholder="Initial login password"
                  value={borrowerForm.password}
                  onChange={(e) => setBorrowerForm({ ...borrowerForm, password: e.target.value })}
                />
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowBorrowerModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="submit-btn" disabled={formSubmitting}>
                  {formSubmitting ? 'Creating...' : 'Create Borrower'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── MODAL: Record Past / Offline Payment ─────────────────── */}
      {showPastPaymentModal && pastPaymentLoan && (
        <div className="modal-backdrop" onClick={() => { setShowPastPaymentModal(false); setEditingPastPayment(null); }}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '540px' }}>
            <div className="modal-header">
              <div>
                <span className="section-eyebrow" style={{ color: '#10b981' }}>
                  Admin Action • Loan #{pastPaymentLoan.id}
                </span>
                <h3 className="modal-title">{editingPastPayment ? 'Edit Past / Offline Payment' : 'Record Past / Offline Payment'}</h3>
              </div>
              <button className="modal-close" onClick={() => { setShowPastPaymentModal(false); setEditingPastPayment(null); }}>
                ×
              </button>
            </div>

            {formError && (
              <div className="alert-banner alert-error" style={{ marginBottom: '16px' }}>
                <span>{formError}</span>
              </div>
            )}

            {/* Loan Context Overview */}
            <div
              style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '8px',
                padding: '14px 16px',
                marginBottom: '18px',
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '10px',
                fontSize: '0.85rem',
              }}
            >
              <div>
                <span style={{ color: '#94a3b8', display: 'block', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  Borrower
                </span>
                <strong style={{ color: '#f8fafc', fontSize: '0.95rem' }}>
                  {pastPaymentLoan.borrower?.name || `User #${pastPaymentLoan.borrower_id}`}
                </strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8', display: 'block', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  Total Payable
                </span>
                <strong style={{ color: '#f8fafc', fontSize: '0.95rem' }} className="font-mono">
                  {formatCurrency(pastPaymentLoan.total_payable)}
                </strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8', display: 'block', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  Already Paid
                </span>
                <strong style={{ color: '#34d399', fontSize: '0.95rem' }} className="font-mono">
                  {formatCurrency(pastPaymentLoan.total_paid)}
                </strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8', display: 'block', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  Current Remaining
                </span>
                <strong style={{ color: '#fbbf24', fontSize: '0.95rem' }} className="font-mono">
                  {formatCurrency(pastPaymentLoan.remaining_balance)}
                </strong>
              </div>
            </div>

            <form onSubmit={handleRecordPastPayment} className="modal-form">
              <div className="form-group">
                <label className="form-label">Payment Amount (₹) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={editingPastPayment ? Number(pastPaymentLoan.remaining_balance) + Number(editingPastPayment.amount) : pastPaymentLoan.remaining_balance}
                  required
                  autoFocus
                  className="form-input font-mono"
                  placeholder="e.g. 2500"
                  value={pastPaymentForm.amount}
                  onChange={(e) => setPastPaymentForm({ ...pastPaymentForm, amount: e.target.value })}
                />
                <span style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '4px', display: 'block' }}>
                  Max allowed: {formatCurrency(pastPaymentLoan.remaining_balance)}
                </span>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Payment Date *</label>
                  <input
                    type="date"
                    required
                    className="form-input"
                    value={pastPaymentForm.payment_date}
                    onChange={(e) => {
                      const d = e.target.value;
                      setPastPaymentForm({
                        ...pastPaymentForm,
                        payment_date: d,
                        payment_month: d ? d.slice(0, 7) : pastPaymentForm.payment_month,
                      });
                    }}
                  />
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '4px', display: 'block' }}>
                    When did the borrower pay?
                  </span>
                </div>
                <div className="form-group">
                  <label className="form-label">Payment Month (YYYY-MM) *</label>
                  <input
                    type="text"
                    required
                    pattern="^\d{4}-\d{2}$"
                    placeholder="YYYY-MM"
                    className="form-input font-mono"
                    value={pastPaymentForm.payment_month}
                    onChange={(e) => setPastPaymentForm({ ...pastPaymentForm, payment_month: e.target.value })}
                  />
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '4px', display: 'block' }}>
                    Format: YYYY-MM
                  </span>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Notes / Reference (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., Cash payment received before website setup"
                  value={pastPaymentForm.notes}
                  onChange={(e) => setPastPaymentForm({ ...pastPaymentForm, notes: e.target.value })}
                />
              </div>

              <div
                style={{
                  background: 'rgba(59, 130, 246, 0.08)',
                  border: '1px solid rgba(59, 130, 246, 0.25)',
                  borderRadius: '6px',
                  padding: '10px 12px',
                  fontSize: '0.8rem',
                  color: '#93c5fd',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  marginBottom: '16px',
                }}
              >
                <span>ℹ️</span>
                <span>
                  This immediately logs an approved <strong>VERIFIED</strong> payment and reduces the loan balance. No screenshot proof is needed.
                </span>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => { setShowPastPaymentModal(false); setEditingPastPayment(null); }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="submit-btn"
                  style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}
                  disabled={formSubmitting}
                >
                  {formSubmitting ? 'Saving...' : editingPastPayment ? 'Save Correction' : 'Record Payment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
