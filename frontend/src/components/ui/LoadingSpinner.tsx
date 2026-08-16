// LoadingSpinner — centered spinner with optional label.

interface LoadingSpinnerProps {
  label?: string;
}

export default function LoadingSpinner({ label = 'Loading…' }: LoadingSpinnerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center gap-3 py-12"
      data-testid="loading-spinner"
    >
      <span className="h-8 w-8 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      <span className="text-sm text-slate-500 dark:text-slate-400">{label}</span>
    </div>
  );
}
