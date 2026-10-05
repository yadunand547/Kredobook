import { apiClient } from './api';

/**
 * Borrower Management API Service (Admin Only)
 */

export async function fetchBorrowers() {
  return await apiClient('/borrowers');
}

export async function fetchBorrower(id) {
  return await apiClient(`/borrowers/${id}`);
}

export async function createBorrower(borrowerData) {
  return await apiClient('/borrowers', {
    method: 'POST',
    body: JSON.stringify(borrowerData),
  });
}

export async function updateBorrower(id, borrowerData) {
  return await apiClient(`/borrowers/${id}`, {
    method: 'PUT',
    body: JSON.stringify(borrowerData),
  });
}

export async function deactivateBorrower(id) {
  return await apiClient(`/borrowers/${id}`, {
    method: 'DELETE',
  });
}

export async function deleteBorrower(id) {
  return await apiClient(`/borrowers/${id}/permanent`, {
    method: 'DELETE',
  });
}

