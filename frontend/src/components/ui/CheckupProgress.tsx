// CheckupProgress — animated multi-step progress bar shown while a
// device analysis runs.

import { useEffect, useState } from 'react';

export const CHECKUP_STEPS = [
  'Preparing sample',
  'Running spectroscopy',
  'Mapping biomarkers',
  'Encrypting report',
] as const;

interface CheckupProgressProps {
  /** Total animation duration in milliseconds. */
  durationMs?: number;
  onComplete?: () => void;
}

export default function CheckupProgress({
  durationMs = 15_000,
  onComplete,
}: CheckupProgressProps) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => {
      const elapsed = Date.now() - started;
      const next = Math.min(100, Math.round((elapsed / durationMs) * 100));
      setProgress(next);
      if (next >= 100 && onComplete) {
        window.clearInterval(timer);
        onComplete();
      }
    }, 120);
    return () => window.clearInterval(timer);
  }, [durationMs, onComplete]);

  const stepIndex = Math.min(
    CHECKUP_STEPS.length - 1,
    Math.floor((progress / 100) * CHECKUP_STEPS.length),
  );

  return (
    <div
      className="w-full max-w-md animate-fade-in"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={progress}
      aria-label="Analysis in progress"
      data-testid="checkup-progress"
    >
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span className="font-medium text-brand-700" data-testid="progress-step">
          {CHECKUP_STEPS[stepIndex]}
        </span>
        <span>{progress}%</span>
      </div>
      <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-brand-500 transition-[width] duration-150 ease-linear"
          style={{ width: `${progress}%` }}
        />
      </div>
      <ol className="mt-3 flex justify-between gap-1 text-[10px] text-slate-400">
        {CHECKUP_STEPS.map((step, i) => (
          <li
            key={step}
            className={i <= stepIndex ? 'font-medium text-brand-600' : undefined}
          >
            {step}
          </li>
        ))}
      </ol>
    </div>
  );
}
