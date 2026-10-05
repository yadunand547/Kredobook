import { apiClient } from './api';

/**
 * Monthly Email Reminder API Service
 */

export async function triggerMonthlyReminders(month) {
  const query = month ? `?month=${encodeURIComponent(month)}` : '';
  return await apiClient(`/reminders/send-monthly${query}`, {
    method: 'POST',
  });
}

export async function fetchReminderLogs(month) {
  const query = month ? `?month=${encodeURIComponent(month)}` : '';
  return await apiClient(`/reminders/logs${query}`);
}

export async function toggleBorrowerReminder(borrowerId, enabled) {
  return await apiClient(`/borrowers/${borrowerId}/reminders`, {
    method: 'PATCH',
    body: JSON.stringify({ enabled }),
  });
}
