// Welcome page tests: form validation and create-user flow with a mocked API.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import Welcome from '../../src/pages/Welcome';
import { UserProvider } from '../../src/context/UserContext';

const API = 'http://localhost:8000';

const mockUser = {
  id: 'user-123',
  age: 34,
  sex: 'female',
  height_cm: 165,
  weight_kg: 62,
  activity_level: 'moderate',
  share_data: false,
  token_balance: 0,
  device_id: 'doctordrobe_demo_001',
  created_at: '2026-07-31T10:00:00Z',
};

function renderWelcome() {
  return render(
    <UserProvider>
      <MemoryRouter initialEntries={['/welcome']}>
        <Welcome />
      </MemoryRouter>
    </UserProvider>,
  );
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByTestId('welcome-age'), '34');
  await user.type(screen.getByTestId('welcome-height'), '165');
  await user.type(screen.getByTestId('welcome-weight'), '62');
}

describe('Welcome', () => {
  it('renders the onboarding form', () => {
    renderWelcome();
    expect(
      screen.getByRole('heading', { name: /let's get to know you/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId('welcome-submit')).toBeInTheDocument();
  });

  it('shows validation errors for invalid input and does not call the API', async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderWelcome();

    await user.type(screen.getByTestId('welcome-age'), '999');
    await user.click(screen.getByTestId('welcome-submit'));

    expect(
      await screen.findByText('Age must be between 1 and 120'),
    ).toBeInTheDocument();
    expect(await screen.findByText(/Height must be between/i)).toBeInTheDocument();
    expect(await screen.findByText(/Weight must be between/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('submits the form and creates a user via the API', async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockUser), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    renderWelcome();

    await fillValidForm(user);
    await user.click(screen.getByTestId('welcome-submit'));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(1);
      const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
      expect(url).toBe(`${API}/api/users`);
      expect(init.method).toBe('POST');
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      expect(body).toMatchObject({ age: 34, height_cm: 165, weight_kg: 62 });
    });

    // Session persisted for the router guard.
    expect(localStorage.getItem('doctordrobe_user_id')).toBe('user-123');
  });

  it('shows an API error message when creation fails', async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Could not create user' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    renderWelcome();

    await fillValidForm(user);
    await user.click(screen.getByTestId('welcome-submit'));

    expect(await screen.findByTestId('welcome-error')).toHaveTextContent(
      'Could not create user',
    );
  });
});
