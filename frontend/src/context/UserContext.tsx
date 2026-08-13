// User session context.
//
// Identity is an email + password. Register/login return an opaque bearer
// token (stored in localStorage) plus the profile; on startup the context
// re-hydrates the profile from GET /api/auth/me. `login`, `logout` and
// `refreshUser` manage the session. Logout best-effort revokes the token
// server-side before clearing local state.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api, setAuthToken } from '../api/client';
import { ApiError } from '../api/client';
import type { User } from '../types';

interface UserContextValue {
  /** Full profile, or null when logged out. */
  user: User | null;
  /** True while the profile is being re-hydrated from the API. */
  loading: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const UserContext = createContext<UserContextValue | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const refreshUser = useCallback(async () => {
    if (!localStorage.getItem('doctordrobe_token')) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const profile = await api.getMe();
      setUser(profile);
    } catch (err) {
      // Stale or revoked token (session expired, password changed
      // elsewhere, account deleted): clear it and sign out.
      if (err instanceof ApiError && err.status === 401) {
        setAuthToken(null);
        setUser(null);
      } else {
        // Network trouble: keep the session but surface the failure via
        // the page-level error paths; do not log the user out.
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const login = useCallback((token: string, profile: User) => {
    setAuthToken(token);
    setUser(profile);
  }, []);

  const logout = useCallback(() => {
    // Best-effort server-side revocation; local state is cleared either way.
    void api.logout().catch(() => undefined);
    setAuthToken(null);
    setUser(null);
  }, []);

  const value = useMemo<UserContextValue>(
    () => ({ user, loading, login, logout, refreshUser }),
    [user, loading, login, logout, refreshUser],
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUserContext(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) {
    throw new Error('useUserContext must be used inside a <UserProvider>');
  }
  return ctx;
}
