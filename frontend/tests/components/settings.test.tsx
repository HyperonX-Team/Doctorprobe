// Settings page tests: profile fields, personalized reference ranges, save.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect } from 'react';
import Settings from '../../src/pages/Settings';
import { UserProvider, useUserContext } from '../../src/context/UserContext';
import { ToastProvider } from '../../src/components/ui/Toast';
import type { User } from '../../src/types';

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

function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

function AuthedHarness({ children }: { children: React.ReactNode }) {
  const { login } = useUserContext();
  useEffect(() => {
    login('token-abc', mockUser);
  }, [login]);
  return <>{children}</>;
}

function renderSettings() {
  localStorage.setItem('doctordrobe_token', 'token-abc');
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.includes('/api/auth/me') && init?.method === 'PUT') {
      return json({ ...mockUser, reference_ranges: { glucose: { low: 1, high: 6 } } });
    }
    if (url.includes('/api/auth/me')) {
      return json(mockUser);
    }
    if (url.includes('/api/devices/status')) {
      return json({ connected: true, last_seen: '2026-08-15T09:00:00Z' });
    }
    if (url.includes('/api/devices/latest')) {
      return json({
        id: 'r1',
        device_id: 'doctordrobe_demo_001',
        rgb_r: 120,
        rgb_g: 200,
        rgb_b: 60,
        temperature_c: 24.5,
        humidity_pct: 45.0,
        created_at: '2026-08-15T09:00:00Z',
      });
    }
    if (url.includes('/api/devices/baseline')) {
      return json(
        {
          id: 'b1',
          device_id: 'doctordrobe_demo_001',
          rgb_r: 240,
          rgb_g: 250,
          rgb_b: 230,
          created_at: '2026-08-01T09:00:00Z',
          updated_at: '2026-08-01T09:00:00Z',
        },
        404,
      );
    }
    throw new Error(`Unexpected fetch call: ${url}`);
  });
  return render(
    <UserProvider>
      <ToastProvider>
        <MemoryRouter initialEntries={['/settings']}>
          <AuthedHarness>
            <Settings />
          </AuthedHarness>
        </MemoryRouter>
      </ToastProvider>
    </UserProvider>,
  );
}

describe('Settings', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders profile fields prefilled from the user', async () => {
    renderSettings();
    expect(await screen.findByTestId('settings-age')).toHaveValue(34);
    expect(screen.getByTestId('settings-height')).toHaveValue(165);
    expect(screen.getByTestId('settings-weight')).toHaveValue(62);
    expect(screen.getByTestId('settings-device-id')).toHaveValue('doctordrobe_demo_001');
  });

  it('saves profile changes and reference ranges together', async () => {
    renderSettings();
    await screen.findByTestId('settings-age');

    fireEvent.change(screen.getByTestId('settings-age'), { target: { value: '35' } });
    fireEvent.change(screen.getByTestId('settings-range-glucose-low'), {
      target: { value: '1' },
    });
    // Wait for the controlled inputs to re-render before submitting.
    await waitFor(() => expect(screen.getByTestId('settings-age')).toHaveValue(35));
    fireEvent.click(screen.getByTestId('settings-save'));

    await waitFor(() => {
      const calls = vi.mocked(globalThis.fetch).mock.calls.map(
        ([input, init]) => [String(input), init] as [string, RequestInit | undefined],
      );
      const saveCall = calls.find(
        ([url, init]) => url.includes('/api/auth/me') && init?.method === 'PUT',
      );
      const body = JSON.parse(String(saveCall?.[1]?.body ?? '{}'));
      expect(body.age).toBe(35);
      expect(body.reference_ranges).toEqual({ glucose: { low: 1, high: 7 } });
    });
  });
});
