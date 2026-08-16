// NotificationBell — in-app notification center for the header.
//
// Polls /api/notifications every 30s, shows an unread-count badge on the
// bell, and opens a drawer with the newest notifications and a
// "mark all read" action. Clicking a reminder takes the user to the
// checkup flow.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { formatDate } from '../../utils/formatters';
import { getErrorMessage } from '../../utils/errors';
import type { AppNotification } from '../../types';

const POLL_INTERVAL_MS = 30_000;

const KIND_LABEL: Record<string, string> = {
  quality: 'Quality',
  trend: 'Trend',
  reminder: 'Reminder',
  reward: 'Reward',
};

export default function NotificationBell() {
  const navigate = useNavigate();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [marking, setMarking] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const response = await api.getNotifications();
      setItems(response.items);
      setUnread(response.unread_count);
      setError(null);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [load]);

  // Close the drawer when clicking outside of it.
  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (drawerRef.current && !drawerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  const handleMarkAllRead = async () => {
    setMarking(true);
    try {
      const response = await api.markNotificationsRead();
      setItems(response.items);
      setUnread(response.unread_count);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setMarking(false);
    }
  };

  return (
    <div className="relative" ref={drawerRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label={unread > 0 ? `${unread} unread notifications` : 'Notifications'}
        data-testid="notification-bell"
        className="relative rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
      >
        🔔
        {unread > 0 && (
          <span
            data-testid="notification-badge"
            className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white"
          >
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          data-testid="notification-drawer"
          className="absolute right-0 z-40 mt-2 w-80 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900"
        >
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-800">
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              Notifications
              {unread > 0 && (
                <span className="ml-2 rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-700 dark:bg-rose-900/40 dark:text-rose-300">
                  {unread} new
                </span>
              )}
            </p>
            <button
              type="button"
              onClick={() => void handleMarkAllRead()}
              disabled={marking || unread === 0}
              data-testid="notification-mark-read"
              className="text-xs font-semibold text-brand-700 hover:underline disabled:cursor-not-allowed disabled:opacity-50 dark:text-brand-300"
            >
              {marking ? 'Marking…' : 'Mark all read'}
            </button>
          </div>

          <div className="max-h-80 overflow-y-auto">
            {loading && items.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-slate-400">Loading…</p>
            )}
            {!loading && items.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-slate-400">
                No notifications yet. Checkups, trends and rewards will show up here.
              </p>
            )}
            {error && (
              <p className="px-4 py-4 text-xs text-rose-600 dark:text-rose-400">
                {error}
              </p>
            )}
            {items.map((notification) => (
              <button
                key={notification.id}
                type="button"
                onClick={() => {
                  setOpen(false);
                  if (notification.kind === 'reminder') {
                    navigate('/checkup');
                  }
                }}
                className={`block w-full border-b border-slate-50 px-4 py-3 text-left hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800 ${
                  notification.read_at ? 'opacity-70' : ''
                }`}
                data-testid="notification-item"
              >
                <span className="text-[10px] font-bold uppercase tracking-wide text-brand-600 dark:text-brand-300">
                  {KIND_LABEL[notification.kind] ?? notification.kind}
                </span>
                <p className="mt-0.5 text-xs text-slate-700 dark:text-slate-200">
                  {notification.message}
                </p>
                <p className="mt-1 text-[10px] text-slate-400">
                  {formatDate(notification.created_at)}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
