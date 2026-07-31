// History — list of past checkups with view/delete actions.

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { useToast } from '../components/ui/Toast';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import type { CheckupSummary } from '../types';
import { formatDate, riskBadgeClasses } from '../utils/formatters';
import { getErrorMessage } from '../utils/errors';

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; checkups: CheckupSummary[] };

export default function History() {
  const { user } = useUser();
  const toast = useToast();
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const [pendingDelete, setPendingDelete] = useState<CheckupSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    if (!user) {
      return;
    }
    setState({ kind: 'loading' });
    try {
      const checkups = await api.listCheckups(user.id);
      setState({ kind: 'ready', checkups });
    } catch (err) {
      setState({ kind: 'error', message: getErrorMessage(err) });
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDelete = async () => {
    if (!user || !pendingDelete) {
      return;
    }
    setDeleting(true);
    try {
      await api.deleteCheckup(pendingDelete.id, user.id);
      toast.show('Checkup deleted', 'success');
      setPendingDelete(null);
      await load();
    } catch (err) {
      toast.show(getErrorMessage(err), 'error');
    } finally {
      setDeleting(false);
    }
  };

  if (!user) {
    return null;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Checkup history</h1>
        <p className="mt-1 text-sm text-slate-500">
          Every analysis you've run, newest first.
        </p>
      </div>

      {state.kind === 'loading' && <LoadingSpinner label="Loading history…" />}

      {state.kind === 'error' && (
        <div
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
        >
          {state.message}
        </div>
      )}

      {state.kind === 'ready' && state.checkups.length === 0 && (
        <div
          className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center"
          data-testid="history-empty"
        >
          <p className="text-sm font-medium text-slate-600">No checkups yet</p>
          <p className="mt-1 text-sm text-slate-400">
            Run your first analysis to see it here.
          </p>
          <Link
            to="/checkup"
            className="mt-4 inline-block rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
          >
            Run a checkup
          </Link>
        </div>
      )}

      {state.kind === 'ready' && state.checkups.length > 0 && (
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {state.checkups.map((checkup) => (
            <li
              key={checkup.id}
              className="flex flex-wrap items-center gap-3 px-4 py-3"
              data-testid="history-row"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800">
                  {formatDate(checkup.created_at)}
                  {checkup.is_shared && (
                    <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
                      shared
                    </span>
                  )}
                </p>
                <p className="mt-0.5 truncate text-xs text-slate-500">
                  {checkup.summary}
                </p>
              </div>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${riskBadgeClasses(checkup.overall_risk)}`}
              >
                {checkup.overall_risk.toUpperCase()}
              </span>
              <div className="flex gap-2">
                <Link
                  to={`/report/${checkup.id}`}
                  className="rounded-lg bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-700 hover:bg-brand-100"
                >
                  View
                </Link>
                <button
                  type="button"
                  onClick={() => setPendingDelete(checkup)}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-rose-50 hover:text-rose-700"
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete this checkup?"
        message="This removes the report from your history. This action cannot be undone."
        confirmLabel="Delete"
        busy={deleting}
        onConfirm={() => void handleDelete()}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
