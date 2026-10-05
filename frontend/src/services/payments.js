import { apiClient, getStoredToken } from './api';
import { API_BASE_URL } from '../utils/constants';

/**
 * Payment API Service
 */

// ── Borrower Operations ─────────────────────────────────────────────
export async function submitPayment({ loan_id, amount, payment_month, payment_date, screenshotFile }) {
  const formData = new FormData();
  formData.append('loan_id', String(loan_id));
  formData.append('amount', String(amount));
  formData.append('payment_month', String(payment_month));
  formData.append('payment_date', String(payment_date));
  formData.append('screenshot', screenshotFile);

  return await apiClient('/payments', {
    method: 'POST',
    body: formData,
  });
}

export async function fetchMyPayments() {
  return await apiClient('/my/payments');
}

export async function fetchMyLoanPayments(loanId) {
  return await apiClient(`/my/loans/${loanId}/payments`);
}

// ── Admin Operations ────────────────────────────────────────────────
export async function fetchAllPayments(status) {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  return await apiClient(`/payments${query}`);
}

export async function fetchPendingPayments() {
  return await apiClient('/payments/pending');
}

export async function approvePayment(paymentId) {
  return await apiClient(`/payments/${paymentId}/approve`, {
    method: 'POST',
  });
}

export async function rejectPayment(paymentId, rejectionReason) {
  return await apiClient(`/payments/${paymentId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ rejection_reason: rejectionReason }),
  });
}

export async function fetchLoanPayments(loanId) {
  return await apiClient(`/loans/${loanId}/payments`);
}

export async function adminRecordPayment({ loan_id, amount, payment_month, payment_date, notes }) {
  return await apiClient('/payments/admin-record', {
    method: 'POST',
    body: JSON.stringify({ loan_id, amount, payment_month, payment_date, notes }),
  });
}

export async function updateAdminRecordedPayment(paymentId, { amount, payment_month, payment_date, notes }) {
  return await apiClient(`/payments/${paymentId}/admin-record`, {
    method: 'PATCH',
    body: JSON.stringify({ amount, payment_month, payment_date, notes }),
  });
}

export async function fetchPayment(paymentId) {
  return await apiClient(`/payments/${paymentId}`);
}

// ── Secure Screenshot Fetcher ───────────────────────────────────────
export async function fetchScreenshotBlobUrl(paymentId) {
  const token = getStoredToken();
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/payments/${paymentId}/screenshot`, {
    headers,
  });

  if (!response.ok) {
    throw new Error('Failed to load screenshot. You may not be authorized to view it.');
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
