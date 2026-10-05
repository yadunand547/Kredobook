import { apiClient } from './api';

/**
 * Loan Management API Service
 */

// ── Admin endpoints ─────────────────────────────────────────────
export async function createLoan(loanData) {
  return await apiClient('/loans', {
    method: 'POST',
    body: JSON.stringify(loanData),
  });
}

export async function fetchLoans() {
  return await apiClient('/loans');
}

export async function fetchLoan(id) {
  return await apiClient(`/loans/${id}`);
}

export async function updateLoan(id, loanData) {
  return await apiClient(`/loans/${id}`, {
    method: 'PUT',
    body: JSON.stringify(loanData),
  });
}

export async function deleteLoan(id) {
  return await apiClient(`/loans/${id}`, {
    method: 'DELETE',
  });
}

export async function fetchAdminDashboardStats() {
  return await apiClient('/loans/stats');
}

// ── Borrower endpoints ──────────────────────────────────────────
export async function fetchMyLoans() {
  return await apiClient('/my/loans');
}

export async function fetchMyLoan(id) {
  return await apiClient(`/my/loans/${id}`);
}

export async function fetchMyStats() {
  return await apiClient('/my/stats');
}
