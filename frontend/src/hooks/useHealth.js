import { useState, useEffect, useCallback } from 'react';
import { fetchHealthStatus } from '../services/api';

/**
 * Custom hook to monitor API and database health
 */
export function useHealth() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastChecked, setLastChecked] = useState(null);

  const checkHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchHealthStatus();
      setHealth(data);
      setLastChecked(new Date());
    } catch (err) {
      setError(err.message || 'Failed to connect to backend server');
      setHealth(null);
      setLastChecked(new Date());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  return { health, loading, error, lastChecked, refetch: checkHealth };
}
