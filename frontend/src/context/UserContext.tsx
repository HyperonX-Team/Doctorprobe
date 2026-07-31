// User session context.
//
// The user id lives in localStorage (no passwords in this system). On
// startup the context re-hydrates the profile from the API; `login`,
// `logout` and `refreshUser` manage the session.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api } from '../api/client';
import type { User } from '../types';

const STORAGE_KEY = 'doctordrobe_user_id';

interface UserContextValue {
  /** Full profile, or null when logged out. */
  user: User | null;
  /** True while the profile is being re-hydrated from the API. */
  loading: boolean;
  login: (user: User) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const UserContext = createContext<UserContextValue | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const refreshUser = useCallback(async () => {
    const storedId = localStorage.getItem(STORAGE_KEY);
    if (!storedId) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const profile = await api.getUser(storedId);
      setUser(profile);
    } catch {
      // Stale or invalid id (e.g. account deleted elsewhere): clear it.
      localStorage.removeItem(STORAGE_KEY);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const login = useCallback((profile: User) => {
    localStorage.setItem(STORAGE_KEY, profile.id);
    setUser(profile);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
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
