// Calibration — dashboard for the SaliNet retraining workflow.
//
// Shows how many labeled samples exist per analyte (vs the trainer's
// 15-sample threshold), the current model's training source and metrics,
// and offers the export/clear actions of the calibration API.

import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { useToast } from '../components/ui/Toast';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import type { AnalyteCalibrationStats, CalibrationStats } from '../types';
import { formatNumber } from '../utils/formatters';
import { getErrorMessage } from '../utils/errors';

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; stats: CalibrationStats };

const STEPS = [
  'Arm the firmware: `CAL <analyte> <concentration>` in the serial monitor.',
  'Put a control strip under the sensor and press the button to capture a labeled sample.',
  'Repeat across concentration levels until every analyte reaches 15 samples.',
  'Export the training CSV below and run `python scripts/train_model.py`.',
  'Verify: run a checkup on a known control and compare against the standard.',
];

export default function Calibration() {
  const { user } = useUser();
  const toast = useToast();
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const [exporting, setExporting] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearing, setClearing] = useState(false);

  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const stats = await api.getCalibrationStats();
      setState({ kind: 'ready', stats });
    } catch (err) {
      setState({ kind: 'error', message: getErrorMessage(err) });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await api.exportCalibrationCsv();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'real_training.csv';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      toast.show('Training CSV exported', 'success');
    } catch (err) {
      toast.show(getErrorMessage(err), 'error');
    } finally {
      setExporting(false);
    }
  };

  const handleClear = async () => {
    setClearing(true);
    try {
      await api.clearCalibrationSamples();
      toast.show('Calibration samples cleared', 'success');
      setConfirmClear(false);
      await load();
    } catch (err) {
      toast.show(getErrorMessage(err), 'error');
    } finally {
      setClearing(false);
    }
  };

  if (!user) {
    return null;
  }

  const analyteCard = (analyte: AnalyteCalibrationStats, key: string) => {
    const target = state.kind === 'ready' ? state.stats.min_real_samples : 15;
    const pct = Math.min(100, Math.round((analyte.count / target) * 100));
    const envelope =
      analyte.min_concentration != null
        ? `${formatNumber(analyte.min_concentration)} – ${formatNumber(analyte.max_concentration ?? analyte.min_concentration)} ${analyte.unit}`
        : '—';
    const sourceReal = analyte.model_source === 'real';

    return (
      <section
        key={key}
        className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900"
        data-testid={`calibration-analyte-${key}`}
      >
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-semibold text-slate-800">{analyte.name}</h3>
          <span
            className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${
              analyte.enough
                ? 'bg-emerald-100 text-emerald-800'
                : 'bg-amber-100 text-amber-800'
            }`}
            data-testid={`calibration-enough-${key}`}
          >
            {analyte.enough ? 'Ready to train' : 'Keep collecting'}
          </span>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          <span className="font-semibold text-slate-700">{analyte.count}</span> /{' '}
          {target} samples · {envelope}
        </p>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full ${analyte.enough ? 'bg-emerald-500' : 'bg-amber-400'}`}
            style={{ width: `${pct}%` }}
            data-testid={`calibration-progress-${key}`}
          />
        </div>
        <p className="mt-2 text-[11px] text-slate-400">
          Model trained on:{' '}
          <span
            className={`font-semibold ${sourceReal ? 'text-emerald-700' : 'text-amber-700'}`}
          >
            {sourceReal ? 'real data' : 'synthetic data'}
          </span>
        </p>
      </section>
    );
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Calibration
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Collect labeled samples to retrain SaliNet on real measurements.
        </p>
      </div>

      <div className="rounded-xl border border-brand-200 bg-brand-50 p-5 dark:border-brand-800 dark:bg-brand-950">
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">
          How it works
        </p>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-slate-700">
          {STEPS.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <p className="mt-3 text-[11px] text-slate-500">
          pH is a ratio measurement and never needs calibration. See the Calibration
          protocol in the README for control-standard recipes.
        </p>
      </div>

      {state.kind === 'loading' && (
        <LoadingSpinner label="Loading calibration stats…" />
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
          <div className="grid gap-4 sm:grid-cols-2">
            {Object.entries(state.stats.analytes).map(([key, analyte]) =>
              analyteCard(analyte, key),
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Deployed model
            </p>
            <dl className="mt-2 grid gap-1 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs text-slate-400">Version</dt>
                <dd
                  className="font-medium text-slate-800"
                  data-testid="calibration-model-version"
                >
                  {state.stats.model.model_version ?? '—'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Trained at</dt>
                <dd className="font-medium text-slate-800">
                  {state.stats.model.trained_at
                    ? new Date(state.stats.model.trained_at).toLocaleString()
                    : '—'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Total samples</dt>
                <dd
                  className="font-medium text-slate-800"
                  data-testid="calibration-total"
                >
                  {state.stats.total_samples}
                </dd>
              </div>
            </dl>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void handleExport()}
              disabled={exporting || state.stats.total_samples === 0}
              data-testid="calibration-export"
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {exporting ? 'Exporting…' : 'Export training CSV'}
            </button>
            <button
              type="button"
              onClick={() => setConfirmClear(true)}
              disabled={clearing || state.stats.total_samples === 0}
              data-testid="calibration-clear"
              className="rounded-lg border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Clear samples
            </button>
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirmClear}
        title="Clear all calibration samples?"
        message="This permanently removes every labeled sample. Export the CSV first if you need it."
        confirmLabel="Clear samples"
        busy={clearing}
        onConfirm={() => void handleClear()}
        onCancel={() => setConfirmClear(false)}
      />
    </div>
  );
}
