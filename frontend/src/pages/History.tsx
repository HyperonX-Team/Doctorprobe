// History — paginated list of past checkups with view/delete actions.

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { useToast } from '../components/ui/Toast';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import type { CheckupSummary } from '../types';
import { formatDate, qualityBadgeClasses, riskBadgeClasses } from '../utils/formatters';
import { getErrorMessage } from '../utils/errors';

const PAGE_SIZE = 20;

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; checkups: CheckupSummary[]; total: number };

export default function History() {
  const { user } = useUser();
  const toast = useToast();
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const [pendingDelete, setPendingDelete] = useState<CheckupSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(
    async (offset = 0, append = false) => {
      if (!user) {
        return;
      }
      if (!append) {
        setState({ kind: 'loading' });
      }
      try {
        const { items, total } = await api.listCheckupsPage(PAGE_SIZE, offset);
        setState((current) => ({
          kind: 'ready',
          total,
          checkups:
            append && current.kind === 'ready'
              ? [...current.checkups, ...items]
              : items,
        }));
      } catch (err) {
        setState({ kind: 'error', message: getErrorMessage(err) });
      }
    },
    [user],
  );

  useEffect(() => {
    void load(0, false);
  }, [load]);

  const handleLoadMore = async () => {
    if (state.kind !== 'ready') {
      return;
    }
    setLoadingMore(true);
    try {
      await load(state.checkups.length, true);
    } finally {
      setLoadingMore(false);
    }
  };

  const handleDelete = async () => {
    if (!user || !pendingDelete) {
      return;
    }
    setDeleting(true);
    try {
      await api.deleteCheckup(pendingDelete.id);
      toast.show('Checkup deleted', 'success');
      setPendingDelete(null);
      await load(0, false);
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
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Checkup history
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Every analysis you've run, newest first.
          </p>
        </div>
        {state.kind === 'ready' && state.total > 0 && (
          <span
            className="text-xs font-medium text-slate-400"
            data-testid="history-total"
          >
            {state.total} checkup{state.total === 1 ? '' : 's'} total
          </span>
        )}
      </div>

      {state.kind === 'loading' && <LoadingSpinner label="Loading history…" />}

      {state.kind === 'error' && (
        <div
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
        >
          {state.message}
        </div>
      )}

      {state.kind === 'ready' && state.checkups.length === 0 && (
        <div
          className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900"
          data-testid="history-empty"
        >
          <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
            No checkups yet
          </p>
          <p className="mt-1 text-sm text-slate-400 dark:text-slate-500">
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
        <>
          <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-700 dark:bg-slate-900">
            {state.checkups.map((checkup) => (
              <li
                key={checkup.id}
                className="flex flex-wrap items-center gap-3 px-4 py-3"
                data-testid="history-row"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                    {formatDate(checkup.created_at)}
                    {checkup.is_shared && (
                      <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                        shared
                      </span>
                    )}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
                    {checkup.summary}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${riskBadgeClasses(checkup.overall_risk)}`}
                >
                  {checkup.overall_risk.toUpperCase()}
                </span>
                {checkup.quality_grade && (
                  <span
                    data-testid={`history-quality-${checkup.id}`}
                    className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${qualityBadgeClasses(checkup.quality_grade)}`}
                  >
                    {checkup.quality_grade.toUpperCase()}
                  </span>
                )}
                <div className="flex gap-2">
                  <Link
                    to={`/report/${checkup.id}`}
                    className="rounded-lg bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-700 hover:bg-brand-100 dark:bg-brand-900/40 dark:text-brand-300 dark:hover:bg-brand-900/60"
                  >
                    View
                  </Link>
                  <button
                    type="button"
                    onClick={() => setPendingDelete(checkup)}
                    className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-rose-50 hover:text-rose-700 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-rose-950 dark:hover:text-rose-400"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>

          {state.checkups.length < state.total && (
            <div className="text-center">
              <button
                type="button"
                onClick={() => void handleLoadMore()}
                disabled={loadingMore}
                data-testid="history-load-more"
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                {loadingMore
                  ? 'Loading…'
                  : `Show more (${state.total - state.checkups.length} remaining)`}
              </button>
            </div>
          )}
        </>
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
