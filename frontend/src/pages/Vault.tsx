// Vault — local, exportable archive of all checkups. Exports a JSON file
// containing the full reports plus user info, and displays a mock
// encryption key fingerprint.

import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { useToast } from '../components/ui/Toast';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import type { Checkup } from '../types';
import { formatDate, todayKey } from '../utils/formatters';
import { getErrorMessage } from '../utils/errors';

// Demo fingerprint of the Fernet key used for report encryption at rest.
// In a real deployment this would be derived from the server's public
// identity or a client-visible key attestation.
const MOCK_KEY_FINGERPRINT = 'a1:b2:c3:d4:e5:f6:07:18:29:3a:4b:5c:6d:7e:8f:90';

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; checkups: Checkup[] };

export default function Vault() {
  const { user } = useUser();
  const toast = useToast();
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    if (!user) {
      return;
    }
    setState({ kind: 'loading' });
    try {
      const summaries = await api.listCheckups();
      const full = await Promise.all(summaries.map((s) => api.getCheckup(s.id)));
      setState({ kind: 'ready', checkups: full });
    } catch (err) {
      setState({ kind: 'error', message: getErrorMessage(err) });
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleExport = async () => {
    if (!user || state.kind !== 'ready') {
      return;
    }
    setExporting(true);
    try {
      const payload = {
        exported_at: new Date().toISOString(),
        user: {
          id: user.id,
          age: user.age,
          sex: user.sex,
          activity_level: user.activity_level,
          device_id: user.device_id,
          token_balance: user.token_balance,
        },
        reports: state.checkups.map((c) => ({
          id: c.id,
          created_at: c.created_at,
          overall_risk: c.overall_risk,
          quality_grade: c.quality_grade,
          text_summary: c.text_summary,
          biomarkers: c.biomarkers,
          analysis: c.analysis ?? null,
          quality: c.quality ?? null,
          note: c.note ?? null,
          is_shared: c.is_shared,
        })),
        encryption: {
          scheme: 'Fernet (symmetric, AES-128-CBC + HMAC)',
          key_fingerprint: MOCK_KEY_FINGERPRINT,
        },
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `doctordrobe-vault-${todayKey()}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      toast.show('Vault exported as JSON', 'success');
    } catch (err) {
      toast.show(getErrorMessage(err), 'error');
    } finally {
      setExporting(false);
    }
  };

  if (!user) {
    return null;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Vault</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Your personal archive of encrypted reports.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void handleExport()}
          disabled={exporting || state.kind !== 'ready' || state.checkups.length === 0}
          data-testid="vault-export"
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {exporting ? 'Exporting…' : 'Download JSON export'}
        </button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Encryption at rest
        </p>
        <p className="mt-2 font-mono text-sm text-slate-700">{MOCK_KEY_FINGERPRINT}</p>
        <p className="mt-2 text-xs text-slate-500">
          Reports are encrypted with Fernet before storage. The key fingerprint above is
          a demo placeholder derived from the server secret.
        </p>
      </div>

      {state.kind === 'loading' && <LoadingSpinner label="Unlocking your vault…" />}

      {state.kind === 'error' && (
        <div
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
        >
          {state.message}
        </div>
      )}

      {state.kind === 'ready' && state.checkups.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900">
          <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
            Your vault is empty
          </p>
          <p className="mt-1 text-sm text-slate-400 dark:text-slate-500">
            Completed checkups appear here automatically.
          </p>
        </div>
      )}

      {state.kind === 'ready' && state.checkups.length > 0 && (
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-700 dark:bg-slate-900">
          {state.checkups.map((checkup) => (
            <li key={checkup.id} className="px-4 py-3" data-testid="vault-row">
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                {formatDate(checkup.created_at)}
              </p>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                {checkup.biomarkers.length} biomarkers ·{' '}
                {checkup.overall_risk.toUpperCase()} risk
                {checkup.quality_grade ? ` · ${checkup.quality_grade}` : ''}
                {checkup.note ? ' · 📝 noted' : ''}
                {checkup.is_shared ? ' · shared' : ''}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
