// Login page tests: sign-in flow and error handling with a mocked API.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import Login from '../../src/pages/Login';
import { UserProvider } from '../../src/context/UserContext';

const API = 'http://localhost:8000';

const authResponse = {
  token: 'token-abc',
  user: {
    id: 'user-123',
    email: 'tester@example.com',
    age: 34,
    sex: 'female',
    height_cm: 165,
    weight_kg: 62,
    activity_level: 'moderate',
    share_data: false,
    token_balance: 5,
    device_id: 'doctordrobe_demo_001',
    created_at: '2026-07-31T10:00:00Z',
  },
};

function renderLogin() {
  return render(
    <UserProvider>
      <MemoryRouter initialEntries={['/login']}>
        <Login />
      </MemoryRouter>
    </UserProvider>,
  );
}

describe('Login', () => {
  it('renders the sign-in form', () => {
    renderLogin();
    expect(screen.getByRole('heading', { name: /welcome back/i })).toBeInTheDocument();
    expect(screen.getByTestId('login-submit')).toBeInTheDocument();
  });

  it('logs in and persists the session token', async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(authResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    renderLogin();

    await user.type(screen.getByTestId('login-email'), 'tester@example.com');
    await user.type(screen.getByTestId('login-password'), 'correct-horse-9!');
    await user.click(screen.getByTestId('login-submit'));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(1);
      const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
      expect(url).toBe(`${API}/api/auth/login`);
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      expect(body).toEqual({
        email: 'tester@example.com',
        password: 'correct-horse-9!',
      });
    });

    expect(localStorage.getItem('doctordrobe_token')).toBe('token-abc');
  });

  it('shows the backend error message for bad credentials', async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Incorrect email or password' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    renderLogin();

    await user.type(screen.getByTestId('login-email'), 'tester@example.com');
    await user.type(screen.getByTestId('login-password'), 'wrong-password-1');
    await user.click(screen.getByTestId('login-submit'));

    expect(await screen.findByTestId('login-error')).toHaveTextContent(
      'Incorrect email or password',
    );
    expect(localStorage.getItem('doctordrobe_token')).toBeNull();
  });
});
