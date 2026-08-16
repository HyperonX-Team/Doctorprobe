// Formatting helpers shared across pages.

/**
 * Format an ISO timestamp for display, e.g. "Today · 14:05" or
 * "Yesterday · 09:30" or "Jul 29, 2026 · 18:20".
 */
export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  const now = new Date();
  const time = date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  });
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const dayDiff = Math.round(
    (startOfToday.getTime() - startOfDate.getTime()) / 86400000,
  );

  if (dayDiff === 0) {
    return `Today · ${time}`;
  }
  if (dayDiff === 1) {
    return `Yesterday · ${time}`;
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

/** Tailwind badge classes for measurement quality grades. */
export function qualityBadgeClasses(grade: string): string {
  switch (grade) {
    case 'good':
      return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300';
    case 'fair':
      return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300';
    case 'poor':
      return 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300';
    default:
      return 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300';
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
