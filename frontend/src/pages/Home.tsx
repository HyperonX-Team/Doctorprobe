// Home — greeting, token balance, latest checkup card, device status card.

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { useDeviceStatus } from '../hooks/useDeviceStatus';
import type { CheckupSummary } from '../types';
import { formatDate, riskBadgeClasses } from '../utils/formatters';
import { getErrorMessage } from '../utils/errors';
import DeviceStatus from '../components/ui/DeviceStatus';

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; checkups: CheckupSummary[] };

export default function Home() {
  const { user } = useUser();
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const deviceStatus = useDeviceStatus(user?.device_id);

  useEffect(() => {
    if (!user) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const checkups = await api.listCheckups(user.id);
        if (!cancelled) {
          setState({ kind: 'ready', checkups });
        }
      } catch (err) {
        if (!cancelled) {
          setState({ kind: 'error', message: getErrorMessage(err) });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (!user) {
    return null;
  }

  const latest = state.kind === 'ready' ? (state.checkups[0] ?? null) : null;

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Hello</h1>
        <p className="mt-1 text-sm text-slate-500">
          Ready for today's checkup? Your last analysis was{' '}
          {latest ? formatDate(latest.created_at) : 'never'}.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Token balance
          </p>
          <p className="mt-1 text-3xl font-bold text-slate-900">{user.token_balance}</p>
          <p className="mt-1 text-xs text-slate-500">Earn more by sharing checkups</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Latest checkup
          </p>
          {state.kind === 'loading' ? (
            <p className="mt-1 text-sm text-slate-500 animate-pulse-soft">Loading…</p>
          ) : latest ? (
            <>
              <span
                className={`mt-1 inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${riskBadgeClasses(latest.overall_risk)}`}
              >
                {latest.overall_risk.toUpperCase()} risk
              </span>
              <p className="mt-2 line-clamp-2 text-xs text-slate-500">
                {latest.summary}
              </p>
              <Link
                to={`/report/${latest.id}`}
                className="mt-2 inline-block text-xs font-semibold text-brand-700 hover:underline"
              >
                View report →
              </Link>
            </>
          ) : (
            <>
              <p className="mt-1 text-sm text-slate-500">No checkups yet</p>
              <Link
                to="/checkup"
                className="mt-2 inline-block text-xs font-semibold text-brand-700 hover:underline"
              >
                Run your first →
              </Link>
            </>
          )}
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Device
          </p>
          <div className="mt-2">
            <DeviceStatus
              status={deviceStatus.status}
              loading={deviceStatus.loading}
              error={deviceStatus.error}
            />
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="font-semibold text-slate-800">What would you like to do?</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Link
            to="/checkup"
            className="rounded-xl bg-brand-600 px-5 py-4 text-sm font-semibold text-white hover:bg-brand-700"
          >
            Run a checkup
          </Link>
          <Link
            to="/history"
            className="rounded-xl border border-slate-200 px-5 py-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            View history
          </Link>
        </div>
      </div>

      {state.kind === 'error' && (
        <p
          role="alert"
          className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700"
        >
          {state.message}
        </p>
      )}
    </div>
  );
}
