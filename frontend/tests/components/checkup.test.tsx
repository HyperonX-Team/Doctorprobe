// Checkup page tests: device status banner, scan flow, and the 409
// no-device-reading error path. The API client module is mocked so no
// network calls escape the test.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect } from 'react';
import Checkup from '../../src/pages/Checkup';
import { UserProvider, useUserContext } from '../../src/context/UserContext';
import { ApiError } from '../../src/api/client';
import type { CheckupCreated, User } from '../../src/types';

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

const mockCreated: CheckupCreated = {
  id: 'checkup-1',
  user_id: mockUser.id,
  summary: 'summary',
  overall_risk: 'low',
  quality_grade: 'good',
  created_at: '2026-07-31T10:00:00Z',
  is_shared: false,
};

const { createCheckupMock } = vi.hoisted(() => ({ createCheckupMock: vi.fn() }));
vi.mock('../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api/client')>();
  return { ...actual, api: { ...actual.api, createCheckup: createCheckupMock } };
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/** URL-aware fetch mock: fresh Response per call, correct shapes. */
function mockFetch() {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes('/api/auth/me')) {
      return json(mockUser);
    }
    if (url.includes('/api/devices/status')) {
      return json({ connected: true, last_seen: '2026-07-31T10:00:00Z' });
    }
    throw new Error(`Unexpected fetch call: ${url}`);
  });
}

/** Harness that signs the user in after mount. */
function AuthedHarness({ children }: { children: React.ReactNode }) {
  const { login } = useUserContext();
  useEffect(() => {
    login('token-abc', mockUser);
  }, [login]);
  return <>{children}</>;
}

function renderCheckup() {
  localStorage.setItem('doctordrobe_token', 'token-abc');
  return render(
    <UserProvider>
      <MemoryRouter initialEntries={['/checkup']}>
        <Routes>
          <Route
            path="/checkup"
            element={
              <AuthedHarness>
                <Checkup />
              </AuthedHarness>
            }
          />
          <Route path="/report/:checkupId" element={<div>REPORT PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </UserProvider>,
  );
}

describe('Checkup', () => {
  beforeEach(() => {
    createCheckupMock.mockReset();
    mockFetch();
  });

  it('shows the device status banner', async () => {
    renderCheckup();
    expect(await screen.findByTestId('device-status')).toBeInTheDocument();
    expect(await screen.findByText(/device connected/i)).toBeInTheDocument();
  });

  it('has no simulated mode', async () => {
    renderCheckup();
    expect(await screen.findByTestId('checkup-scan')).toBeInTheDocument();
    expect(screen.queryByTestId('checkup-simulate')).not.toBeInTheDocument();
  });

  it('creates a checkup from the device reading and navigates to the report', async () => {
    const user = userEvent.setup();
    createCheckupMock.mockResolvedValue(mockCreated);

    renderCheckup();
    await user.click(await screen.findByTestId('checkup-scan'));

    await waitFor(() => {
      expect(createCheckupMock).toHaveBeenCalledWith();
    });
    expect(await screen.findByText('REPORT PAGE')).toBeInTheDocument();
  });

  it('handles a 409 when no device reading exists, with retry', async () => {
    const user = userEvent.setup();
    createCheckupMock.mockRejectedValue(
      new ApiError(
        409,
        'No device reading available. Take a reading with your Doctordrobe device first.',
      ),
    );

    renderCheckup();
    await user.click(await screen.findByTestId('checkup-scan'));

    expect(await screen.findByTestId('checkup-error')).toHaveTextContent(
      /no device reading available/i,
    );
    expect(screen.getByTestId('checkup-retry')).toBeInTheDocument();

    // Retry returns to the idle screen; scanning again now succeeds.
    await user.click(screen.getByTestId('checkup-retry'));
    expect(screen.getByTestId('checkup-scan')).toBeInTheDocument();

    createCheckupMock.mockResolvedValue(mockCreated);
    await user.click(screen.getByTestId('checkup-scan'));
    expect(await screen.findByText('REPORT PAGE')).toBeInTheDocument();
  });
});
