// useCheckup hook — loads a full checkup report with loading/error state.

import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Checkup } from '../types';
import { getErrorMessage } from '../utils/errors';

export function useCheckup(checkupId: string | undefined) {
  const [checkup, setCheckup] = useState<Checkup | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!checkupId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCheckup(checkupId);
      setCheckup(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [checkupId]);

  useEffect(() => {
    void load();
  }, [load]);

  return { checkup, loading, error, reload: load };
}
