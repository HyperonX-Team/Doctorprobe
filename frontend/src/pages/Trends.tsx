// Trends — longitudinal view of every marker over the selected window.
//
// Renders a dependency-free SVG line chart per marker (reference range
// band, state-coloured points) plus the deterministic alerts the backend
// derives from the series. A single reading is a snapshot; this page is
// the signal.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { useToast } from '../components/ui/Toast';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import type { MarkerTrend, TrendsResponse } from '../types';
import { formatDate, formatNumber, stateBadgeClasses } from '../utils/formatters';
import { getErrorMessage } from '../utils/errors';

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; trends: TrendsResponse };

const WINDOWS = [
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
  { days: 365, label: '1 year' },
];

const WINDOW_KEY = 'doctordrobe_trends_window';

const WIDTH = 640;
const HEIGHT = 180;
const PAD_X = 8;
const PAD_Y = 12;

function LineChart({ marker }: { marker: MarkerTrend }) {
  const points = marker.points;
  const values = points.map((p) => p.value);

  const [minValue, maxValue] = useMemo(() => {
    const lo = Math.min(...values, marker.ref_low ?? Infinity);
    const hi = Math.max(...values, marker.ref_high ?? -Infinity);
    const span = hi - lo || 1;
    const pad = span * 0.1;
    return [lo - pad, hi + pad];
  }, [values, marker.ref_low, marker.ref_high]);

  const x = (i: number) =>
    PAD_X + (i / Math.max(points.length - 1, 1)) * (WIDTH - 2 * PAD_X);
  const y = (v: number) =>
    HEIGHT -
    PAD_Y -
    ((v - minValue) / (maxValue - minValue || 1)) * (HEIGHT - 2 * PAD_Y);

  const line = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`)
    .join(' ');

  const bandTop = marker.ref_high != null ? y(marker.ref_high) : PAD_Y;
  const bandBottom = marker.ref_low != null ? y(marker.ref_low) : HEIGHT - PAD_Y;

  return (
    <div className="mt-4">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-44 w-full"
        role="img"
        aria-label={`${marker.name} trend chart`}
        data-testid={`trend-chart-${marker.key}`}
      >
        <rect
          x={PAD_X}
          y={bandTop}
          width={WIDTH - 2 * PAD_X}
          height={Math.max(bandBottom - bandTop, 0)}
          className="fill-emerald-50"
        />
        <line
          x1={PAD_X}
          x2={WIDTH - PAD_X}
          y1={y(0)}
          y2={y(0)}
          stroke="currentColor"
          className="text-slate-200"
          strokeWidth="1"
        />
        <path d={line} fill="none" strokeWidth="2" className="stroke-brand-600" />
        {points.map((p, i) => (
          <circle
            key={`${p.date}-${i}`}
            cx={x(i)}
            cy={y(p.value)}
            r="4"
            className={stateBadgeClasses(p.state).split(' ')[0]}
            stroke="white"
            strokeWidth="1.5"
          >
            <title>
              {formatDate(p.date)} — {formatNumber(p.value)} {p.unit} ({p.state})
            </title>
          </circle>
        ))}
        {marker.ref_low != null && marker.ref_high != null && (
          <text
            x={WIDTH - PAD_X}
            y={bandTop - 4}
            textAnchor="end"
            className="fill-slate-400 text-[11px]"
          >
            ref {formatNumber(marker.ref_low)}–{formatNumber(marker.ref_high)}{' '}
            {marker.unit}
          </text>
        )}
        {points.length > 1 && (
          <>
            <text x={PAD_X} y={HEIGHT - 2} className="fill-slate-400 text-[11px]">
              {formatDate(points[0].date)}
            </text>
            <text
              x={WIDTH - PAD_X}
              y={HEIGHT - 2}
              textAnchor="end"
              className="fill-slate-400 text-[11px]"
            >
              {formatDate(points[points.length - 1].date)}
            </text>
          </>
        )}
      </svg>
    </div>
  );
}

function MarkerCard({ marker }: { marker: MarkerTrend }) {
  const hasData = marker.points.length > 0;
  const stateBadge = (state: string) =>
    stateBadgeClasses(state as 'low' | 'normal' | 'high');

  return (
    <section
      className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900"
      data-testid={`trend-marker-${marker.key}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-slate-800 dark:text-slate-100">
          {marker.name}
        </h2>
        {marker.stats && (
          <span className="text-xs text-slate-500">
            latest {formatNumber(marker.stats.latest)} {marker.unit} · mean{' '}
            {formatNumber(marker.stats.mean)}
          </span>
        )}
      </div>

      {!hasData && (
        <p className="mt-3 text-sm text-slate-400 dark:text-slate-500">
          No checkups in this window yet.
        </p>
      )}

      {hasData && (
        <>
          <LineChart marker={marker} />
          <div className="mt-3 flex flex-wrap gap-1.5">
            {marker.points.map((p, i) => (
              <span
                key={`${p.date}-${i}`}
                className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${stateBadge(p.state)}`}
                title={formatDate(p.date)}
              >
                {p.state}
              </span>
            ))}
          </div>
        </>
      )}

      {marker.alerts.length > 0 && (
        <ul className="mt-4 space-y-2">
          {marker.alerts.map((alert) => (
            <li
              key={alert.type}
              data-testid={`trend-alert-${marker.key}`}
              className={`rounded-lg px-3 py-2 text-xs ${
                alert.severity === 'warning'
                  ? 'bg-amber-50 text-amber-800'
                  : 'bg-slate-50 text-slate-600'
              }`}
            >
              <span className="font-semibold uppercase tracking-wide">
                {alert.type.replace(/_/g, ' ')}
              </span>
              <span className="mt-0.5 block">{alert.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function storedWindow(): number {
  const raw = Number(localStorage.getItem(WINDOW_KEY));
  return WINDOWS.some((window) => window.days === raw) ? raw : 30;
}

export default function Trends() {
  const { user } = useUser();
  const toast = useToast();
  const [windowDays, setWindowDays] = useState(storedWindow);
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const [exporting, setExporting] = useState(false);

  const handleWindowChange = (days: number) => {
    localStorage.setItem(WINDOW_KEY, String(days));
    setWindowDays(days);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await api.exportTrends(windowDays);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `doctordrobe-trends-${windowDays}d.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      toast.show('Trends exported as CSV', 'success');
    } catch (err) {
      toast.show(getErrorMessage(err), 'error');
    } finally {
      setExporting(false);
    }
  };

  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const trends = await api.getTrends(windowDays);
      setState({ kind: 'ready', trends });
    } catch (err) {
      setState({ kind: 'error', message: getErrorMessage(err) });
    }
  }, [windowDays]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!user) {
    return null;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 animate-fade-in">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Trends</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            How your markers move over time — built from your checkups.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void handleExport()}
            disabled={
              exporting || state.kind !== 'ready' || state.trends.checkup_count === 0
            }
            data-testid="trends-export"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {exporting ? 'Exporting…' : 'Export CSV'}
          </button>
          <div className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1 dark:border-slate-700 dark:bg-slate-900">
            {WINDOWS.map((window) => (
              <button
                key={window.days}
                type="button"
                onClick={() => handleWindowChange(window.days)}
                data-testid={`trends-window-${window.days}`}
                className={`rounded-md px-3 py-1.5 text-xs font-semibold ${
                  windowDays === window.days
                    ? 'bg-brand-600 text-white'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`}
              >
                {window.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {state.kind === 'loading' && <LoadingSpinner label="Building your trends…" />}

      {state.kind === 'error' && (
        <div
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
        >
          {state.message}
        </div>
      )}

      {state.kind === 'ready' && state.trends.checkup_count === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <p className="text-sm font-medium text-slate-600">No checkups yet</p>
          <p className="mt-1 text-sm text-slate-400">
            Trends need at least a few checkups to show a signal. Run a checkup and come
            back.
          </p>
        </div>
      )}

      {state.kind === 'ready' && state.trends.checkup_count > 0 && (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Checkups in window
              </p>
              <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-white">
                {state.trends.checkup_count}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Alerts
              </p>
              <p
                className={`mt-1 text-2xl font-bold ${
                  state.trends.alert_count > 0
                    ? 'text-amber-600'
                    : 'text-slate-900 dark:text-white'
                }`}
              >
                {state.trends.alert_count}
              </p>
            </div>
          </div>

          <div className="space-y-4">
            {Object.values(state.trends.markers).map((marker) => (
              <MarkerCard key={marker.key} marker={marker} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
