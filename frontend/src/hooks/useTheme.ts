// useTheme — dark mode support.
//
// Modes: 'light' | 'dark' | 'system'. The effective theme follows the OS
// preference when set to 'system' (and reacts to live changes), otherwise
// the manual choice. The choice is persisted in localStorage and applied
// by toggling the `dark` class on <html> for Tailwind's `dark:` variant.

import { useCallback, useEffect, useState } from 'react';

export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'doctordrobe_theme';

function storedMode(): ThemeMode {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw === 'light' || raw === 'dark' || raw === 'system' ? raw : 'system';
}

function systemTheme(): ResolvedTheme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(mode: ThemeMode): ResolvedTheme {
  const resolved = mode === 'system' ? systemTheme() : mode;
  document.documentElement.classList.toggle('dark', resolved === 'dark');
  return resolved;
}

export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>(storedMode);
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    applyTheme(storedMode()),
  );

  useEffect(() => {
    setResolved(applyTheme(mode));
    if (mode === 'system') {
      // Keep in sync when the OS theme changes while the tab is open.
      const media = window.matchMedia('(prefers-color-scheme: dark)');
      const onChange = () => setResolved(applyTheme('system'));
      media.addEventListener('change', onChange);
      return () => media.removeEventListener('change', onChange);
    }
    return undefined;
  }, [mode]);

  const setModeAndPersist = useCallback((next: ThemeMode) => {
    localStorage.setItem(STORAGE_KEY, next);
    setMode(next);
  }, []);

  return { mode, setMode: setModeAndPersist, resolved };
}
