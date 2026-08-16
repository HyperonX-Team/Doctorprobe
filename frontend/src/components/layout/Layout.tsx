// Layout — shell with navigation header wrapping all logged-in pages.

import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useUser } from '../../hooks/useUser';
import { useTheme, type ThemeMode } from '../../hooks/useTheme';
import { ToastProvider } from '../ui/Toast';
import NotificationBell from '../ui/NotificationBell';

const NAV_ITEMS = [
  { to: '/', label: 'Home', end: true },
  { to: '/checkup', label: 'Checkup' },
  { to: '/history', label: 'History' },
  { to: '/trends', label: 'Trends' },
  { to: '/community', label: 'Community' },
  { to: '/vault', label: 'Vault' },
  { to: '/calibration', label: 'Calibration' },
  { to: '/settings', label: 'Settings' },
];

const THEME_OPTIONS: { value: ThemeMode; label: string }[] = [
  { value: 'light', label: '☀️' },
  { value: 'system', label: '🖥️' },
  { value: 'dark', label: '🌙' },
];

export default function Layout() {
  const { user, logout } = useUser();
  const { mode, setMode } = useTheme();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/welcome');
  };

  return (
    <ToastProvider>
      <div className="min-h-screen bg-slate-50 transition-colors dark:bg-slate-950">
        <header className="border-b border-slate-200 bg-white transition-colors dark:border-slate-800 dark:bg-slate-900">
          <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
                D
              </span>
              <span className="text-lg font-semibold text-slate-900 dark:text-white">
                Doctordrobe
              </span>
              <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
                v2.0
              </span>
            </div>
            <nav className="flex items-center gap-1" aria-label="Main navigation">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `rounded-lg px-3 py-1.5 text-sm font-medium ${
                      isActive
                        ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <div className="flex items-center gap-3">
              {user && (
                <span className="hidden rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 sm:inline-block">
                  {user.token_balance} tokens
                </span>
              )}
              <div
                className="flex gap-0.5 rounded-lg border border-slate-300 p-0.5 dark:border-slate-600"
                role="group"
                aria-label="Theme"
              >
                {THEME_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setMode(option.value)}
                    aria-label={`${option.value} theme`}
                    title={option.value}
                    data-testid={`theme-${option.value}`}
                    className={`rounded-md px-1.5 py-0.5 text-xs ${
                      mode === option.value
                        ? 'bg-brand-600 text-white'
                        : 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <NotificationBell />
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Log out
              </button>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">
          <Outlet />
        </main>
        <footer className="mx-auto max-w-5xl px-4 pb-8 text-center text-xs text-slate-400 dark:text-slate-500">
          Doctordrobe · demo health analyzer · not a medical device
        </footer>
      </div>
    </ToastProvider>
  );
}
