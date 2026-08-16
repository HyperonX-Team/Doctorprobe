// useUser hook tests: re-hydration from the bearer token and login/logout.

import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UserProvider, useUserContext } from '../../src/context/UserContext';
import type { User } from '../../src/types';

const API = 'http://localhost:8000';

const mockUser: User = {
  id: 'user-123',
  email: 'tester@example.com',
  age: 34,
  sex: 'female',
  height_cm: 165,
  weight_kg: 62,
  activity_level: 'moderate',
  share_data: false,
  token_balance: 0,
  device_id: 'doctordrobe_demo_001',
  reference_ranges: null,
  created_at: '2026-07-31T10:00:00Z',
};

function Probe() {
  const { user, loading, login, logout } = useUserContext();
  return (
    <div>
      <p data-testid="loading">{String(loading)}</p>
      <p data-testid="user">{user ? user.id : 'none'}</p>
      <button type="button" onClick={() => login('token-abc', mockUser)}>
        Login
      </button>
      <button type="button" onClick={() => logout()}>
        Logout
      </button>
    </div>
  );
}

function renderProbe() {
  return render(
    <UserProvider>
      <Probe />
    </UserProvider>,
  );
}

describe('useUser', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('starts logged out when no token is stored', async () => {
    renderProbe();
    await waitFor(() =>
      expect(screen.getByTestId('loading')).toHaveTextContent('false'),
    );
    expect(screen.getByTestId('user')).toHaveTextContent('none');
  });

  it('re-hydrates the profile from /api/auth/me when a token is stored', async () => {
    localStorage.setItem('doctordrobe_token', 'token-abc');
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockUser), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    renderProbe();
    await waitFor(() =>
      expect(screen.getByTestId('user')).toHaveTextContent('user-123'),
    );

    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API}/api/auth/me`);
    expect((init.headers as Record<string, string>).Authorization).toBe(
      'Bearer token-abc',
    );
  });

  it('clears a revoked token when /api/auth/me returns 401', async () => {
    localStorage.setItem('doctordrobe_token', 'expired-token');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Session expired' }), { status: 401 }),
    );

    renderProbe();
    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('none'));
    expect(localStorage.getItem('doctordrobe_token')).toBeNull();
  });

  it('login and logout update the session and storage', async () => {
    const user = await import('@testing-library/user-event').then((m) =>
      m.default.setup(),
    );
    // logout best-effort calls POST /api/auth/logout; resolve it silently.
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Logged out' }), { status: 200 }),
    );

    renderProbe();
    await waitFor(() =>
      expect(screen.getByTestId('loading')).toHaveTextContent('false'),
    );

    await user.click(screen.getByText('Login'));
    expect(screen.getByTestId('user')).toHaveTextContent('user-123');
    expect(localStorage.getItem('doctordrobe_token')).toBe('token-abc');

    await act(async () => {
      await user.click(screen.getByText('Logout'));
    });
    expect(screen.getByTestId('user')).toHaveTextContent('none');
    expect(localStorage.getItem('doctordrobe_token')).toBeNull();
  });
});
