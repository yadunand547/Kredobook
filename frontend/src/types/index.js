/**
 * @typedef {Object} HealthResponse
 * @property {string} status - Backend status (e.g. "ok")
 * @property {string} database - Database connection status (e.g. "connected")
 *
 * @typedef {Object} User
 * @property {string} id - UUID
 * @property {string} email
 * @property {string} role - 'ADMIN' | 'BORROWER'
 * @property {string} created_at
 *
 * @typedef {Object} Loan
 * @property {string} id - UUID
 * @property {string} user_id - UUID
 * @property {number} amount - Numeric amount
 * @property {number} interest_rate
 * @property {number} term_months
 * @property {string} status - 'PENDING' | 'APPROVED' | 'REJECTED' | 'PAID'
 * @property {string} created_at
 *
 * @typedef {Object} Payment
 * @property {string} id - UUID
 * @property {string} loan_id - UUID
 * @property {string} user_id - UUID
 * @property {number} amount
 * @property {string} payment_date
 * @property {string} status - 'COMPLETED' | 'FAILED' | 'PENDING'
 */

export const Role = {
  ADMIN: 'ADMIN',
  BORROWER: 'BORROWER',
};

export const LoanStatus = {
  PENDING: 'PENDING',
  APPROVED: 'APPROVED',
  REJECTED: 'REJECTED',
  PAID: 'PAID',
};

export const PaymentStatus = {
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  PENDING: 'PENDING',
};
