// Community — the anonymized Insights marketplace.
//
// Shows server-side cohort aggregates built from shared checkups of
// other users: "you vs similar profiles" per marker (your latest value,
// the cohort median/percentile, the cohort spread). Raw community data
// never leaves the server — only means, percentiles and counts.

import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import type { CommunityInsights, CommunityMarkerInsight } from '../types';
import { formatNumber, stateBadgeClasses } from '../utils/formatters';
import { getErrorMessage } from '../utils/errors';

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; insights: CommunityInsights };

function percentileLabel(percentile: number): string {
  const pct = Math.round(percentile * 100);
  if (pct >= 90) {
    return `higher than ~${100 - pct}% of similar profiles`;
  }
  if (pct <= 10) {
    return `lower than ~${pct}% of similar profiles`;
  }
  return `in line with ~${pct}% of similar profiles`;
}

function MarkerCard({ marker }: { marker: CommunityMarkerInsight }) {
  const hasCohort = marker.cohort_count > 0;
  const hasOwn = marker.user_latest != null;
  const median = marker.cohort_p50;

  return (
    <section
      className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900"
      data-testid={`community-marker-${marker.key}`}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100">
          {marker.name}
        </h3>
        {hasCohort && (
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {marker.cohort_count} shared checkups
          </span>
        )}
      </div>

      {!hasCohort && (
        <p className="mt-3 text-sm text-slate-400">
          No community data for this marker yet — share checkups to grow the cohort.
        </p>
      )}

      {hasCohort && (
        <div className="mt-3 space-y-3">
          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                Your latest
              </p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">
                {hasOwn ? `${formatNumber(marker.user_latest!)} ` : '—'}
                <span className="text-sm font-medium text-slate-400">
                  {marker.unit}
                </span>
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                Community median
              </p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">
                {median != null ? formatNumber(median) : '—'}
                <span className="text-sm font-medium text-slate-400">
                  {' '}
                  {marker.unit}
                </span>
              </p>
            </div>
          </div>

          {hasOwn && marker.user_percentile != null && (
            <p
              className="rounded-lg bg-brand-50 px-3 py-2 text-xs font-medium text-brand-800 dark:bg-brand-900/30 dark:text-brand-200"
              data-testid={`community-percentile-${marker.key}`}
            >
              {percentileLabel(marker.user_percentile)}
            </p>
          )}

          <div>
            <div className="relative h-2 rounded-full bg-slate-100 dark:bg-slate-800">
              {marker.cohort_p10 != null && marker.cohort_p90 != null && (
                <div
                  className="absolute inset-y-0 rounded-full bg-brand-200 dark:bg-brand-800"
                  style={{
                    left: `${((marker.cohort_p10 - (marker.ref_low ?? marker.cohort_p10)) / ((marker.ref_high ?? marker.cohort_p90) - (marker.ref_low ?? marker.cohort_p10)) || 1) * 100}%`,
                    width: `${((marker.cohort_p90 - marker.cohort_p10) / ((marker.ref_high ?? marker.cohort_p90) - (marker.ref_low ?? marker.cohort_p10)) || 0) * 100}%`,
                  }}
                />
              )}
              {hasOwn && marker.user_percentile != null && (
                <span
                  className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-brand-600 shadow dark:border-slate-900"
                  style={{ left: `${marker.user_percentile * 100}%` }}
                  title="Your position within the cohort"
                />
              )}
            </div>
            <div className="mt-1 flex justify-between text-[10px] text-slate-400">
              <span>{marker.ref_low != null ? formatNumber(marker.ref_low) : '—'}</span>
              <span>reference range</span>
              <span>
                {marker.ref_high != null ? formatNumber(marker.ref_high) : '—'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg bg-slate-50 px-2 py-1.5 dark:bg-slate-800">
              <p className="text-[10px] text-slate-400">10th pct</p>
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                {marker.cohort_p10 != null ? formatNumber(marker.cohort_p10) : '—'}
              </p>
            </div>
            <div className="rounded-lg bg-slate-50 px-2 py-1.5 dark:bg-slate-800">
              <p className="text-[10px] text-slate-400">Mean ± SD</p>
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                {marker.cohort_mean != null
                  ? `${formatNumber(marker.cohort_mean)} ± ${formatNumber(marker.cohort_std ?? 0)}`
                  : '—'}
              </p>
            </div>
            <div className="rounded-lg bg-slate-50 px-2 py-1.5 dark:bg-slate-800">
              <p className="text-[10px] text-slate-400">90th pct</p>
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                {marker.cohort_p90 != null ? formatNumber(marker.cohort_p90) : '—'}
              </p>
            </div>
          </div>

          {hasOwn && marker.user_state && (
            <p>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${stateBadgeClasses(marker.user_state as 'low' | 'normal' | 'high')}`}
              >
                your latest: {marker.user_state}
              </span>
            </p>
          )}
        </div>
      )}
    </section>
  );
}

export default function Community() {
  const { user } = useUser();
  const [state, setState] = useState<LoadState>({ kind: 'loading' });

  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const insights = await api.getCommunityInsights();
      setState({ kind: 'ready', insights });
    } catch (err) {
      setState({ kind: 'error', message: getErrorMessage(err) });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!user) {
    return null;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Community Insights
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Anonymized cohort comparisons from shared checkups — how your markers compare
          with similar profiles.
        </p>
      </div>

      {state.kind === 'loading' && (
        <LoadingSpinner label="Gathering community insights…" />
      )}

      {state.kind === 'error' && (
        <div
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
        >
          {state.message}
        </div>
      )}

      {state.kind === 'ready' && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Shared checkups
              </p>
              <p
                className="mt-1 text-3xl font-bold text-slate-900 dark:text-white"
                data-testid="community-cohort-checkups"
              >
                {state.insights.cohort_checkups}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Community members
              </p>
              <p className="mt-1 text-3xl font-bold text-slate-900 dark:text-white">
                {state.insights.cohort_users}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Similar profiles
              </p>
              <p className="mt-1 text-3xl font-bold text-slate-900 dark:text-white">
                {state.insights.similar_profile_count}
              </p>
            </div>
          </div>

          {state.insights.cohort_checkups < state.insights.min_cohort && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
              The community is still growing — at least {state.insights.min_cohort}{' '}
              shared checkups are needed before per-marker comparisons become
              meaningful. Share your checkups to help, and check back soon.
            </div>
          )}

          <div className="space-y-4">
            {Object.values(state.insights.markers).map((marker) => (
              <MarkerCard key={marker.key} marker={marker} />
            ))}
          </div>

          <p className="text-xs text-slate-400 dark:text-slate-500">
            Comparisons use only aggregated statistics — individual shared checkups are
            never exposed. Sharing is always opt-in per checkup on the report page.
          </p>
        </>
      )}
    </div>
  );
}
