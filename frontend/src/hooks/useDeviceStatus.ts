// useDeviceStatus hook — polls the backend for device connectivity.

import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { DeviceStatus } from '../types';

const POLL_INTERVAL_MS = 10_000;

export function useDeviceStatus(deviceId: string | undefined, enabled = true) {
  const [status, setStatus] = useState<DeviceStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!deviceId || !enabled) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    const poll = async () => {
      try {
        const next = await api.getDeviceStatus(deviceId);
        if (!cancelled) {
          setStatus(next);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Status unavailable');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void poll();
    const timer = setInterval(() => void poll(), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [deviceId, enabled]);

  return { status, loading, error };
}
