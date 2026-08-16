// NotificationBell tests: unread badge, drawer list, mark all read.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect } from 'react';
import NotificationBell from '../../src/components/ui/NotificationBell';
import { UserProvider, useUserContext } from '../../src/context/UserContext';
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

function AuthedHarness({ children }: { children: React.ReactNode }) {
  const { login } = useUserContext();
  useEffect(() => {
    login('token-abc', mockUser);
  }, [login]);
  return <>{children}</>;
}

function renderBell() {
  localStorage.setItem('doctordrobe_token', 'token-abc');
  return render(
    <UserProvider>
      <MemoryRouter>
        <AuthedHarness>
          <NotificationBell />
        </AuthedHarness>
      </MemoryRouter>
    </UserProvider>,
  );
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/api/auth/me')) {
        return new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/notifications/read')) {
        const body = {
          unread_count: 0,
          items: [
            {
              id: 'n1',
              kind: 'reward',
              message: 'You shared a checkup and earned 5 tokens.',
              created_at: '2026-08-15T09:00:00Z',
              read_at: '2026-08-15T10:00:00Z',
            },
          ],
        };
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/notifications')) {
        const body = {
          unread_count: 2,
          items: [
            {
              id: 'n2',
              kind: 'reminder',
              message: "It's been 4 days since your last checkup.",
              created_at: '2026-08-15T08:00:00Z',
              read_at: null,
            },
            {
              id: 'n1',
              kind: 'reward',
              message: 'You shared a checkup and earned 5 tokens.',
              created_at: '2026-08-15T09:00:00Z',
              read_at: null,
            },
          ],
        };
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      throw new Error(`Unexpected fetch call: ${url}`);
    });
  });

  it('shows the unread badge and the drawer contents', async () => {
    renderBell();
    expect(await screen.findByTestId('notification-badge')).toHaveTextContent('2');
    await userEvent.click(screen.getByTestId('notification-bell'));
    expect(await screen.findByTestId('notification-drawer')).toBeInTheDocument();
    expect(screen.getAllByTestId('notification-item').length).toBe(2);
    expect(screen.getByText(/4 days since your last checkup/i)).toBeInTheDocument();
  });

  it('marks all read from the drawer', async () => {
    const user = userEvent.setup();
    renderBell();
    await screen.findByTestId('notification-badge');
    await user.click(screen.getByTestId('notification-bell'));
    await user.click(screen.getByTestId('notification-mark-read'));

    await waitFor(() => {
      expect(screen.queryByTestId('notification-badge')).not.toBeInTheDocument();
    });
  });
});
