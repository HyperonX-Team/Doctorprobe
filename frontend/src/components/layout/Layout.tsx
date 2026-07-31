// Layout — shell with navigation header wrapping all logged-in pages.

import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useUser } from '../../hooks/useUser';
import { ToastProvider } from '../ui/Toast';

const NAV_ITEMS = [
  { to: '/', label: 'Home', end: true },
  { to: '/checkup', label: 'Checkup' },
  { to: '/history', label: 'History' },
  { to: '/vault', label: 'Vault' },
  { to: '/settings', label: 'Settings' },
];

export default function Layout() {
  const { user, logout } = useUser();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/welcome');
  };

  return (
    <ToastProvider>
      <div className="min-h-screen bg-slate-50">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
                D
              </span>
              <span className="text-lg font-semibold text-slate-900">Doctordrobe</span>
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
                        ? 'bg-brand-50 text-brand-700'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <div className="flex items-center gap-3">
              {user && (
                <span className="hidden rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 sm:inline-block">
                  {user.token_balance} tokens
                </span>
              )}
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Log out
              </button>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">
          <Outlet />
        </main>
        <footer className="mx-auto max-w-5xl px-4 pb-8 text-center text-xs text-slate-400">
          Doctordrobe · demo health analyzer · not a medical device
        </footer>
      </div>
    </ToastProvider>
  );
}
