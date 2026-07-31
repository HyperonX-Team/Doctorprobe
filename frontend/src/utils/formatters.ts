// Formatting helpers shared across pages.

/** Format an ISO timestamp for display, e.g. "Jul 31, 2026 · 14:05". */
export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Format a number with up to 2 decimals, dropping trailing zeros. */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 2,
  }).format(value);
}

/** Tailwind badge classes for risk levels. */
export function riskBadgeClasses(risk: 'low' | 'medium' | 'high'): string {
  switch (risk) {
    case 'low':
      return 'bg-emerald-100 text-emerald-800';
    case 'medium':
      return 'bg-amber-100 text-amber-800';
    case 'high':
      return 'bg-rose-100 text-rose-800';
  }
}

/** Tailwind badge classes for biomarker states. */
export function stateBadgeClasses(state: 'low' | 'normal' | 'high'): string {
  switch (state) {
    case 'low':
      return 'bg-sky-100 text-sky-800';
    case 'normal':
      return 'bg-emerald-100 text-emerald-800';
    case 'high':
      return 'bg-rose-100 text-rose-800';
  }
}

/** Human label for a risk level. */
export function riskLabel(risk: 'low' | 'medium' | 'high'): string {
  return risk.toUpperCase();
}

/** Date-key for Vault exports, e.g. "2026-07-31". */
export function todayKey(): string {
  return new Date().toISOString().slice(0, 10);
}
