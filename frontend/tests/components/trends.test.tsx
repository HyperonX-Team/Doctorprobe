// Trends page tests: series rendering, alerts, empty state, window switch.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect } from 'react';
import Trends from '../../src/pages/Trends';
import { UserProvider, useUserContext } from '../../src/context/UserContext';
import type { TrendsResponse, User } from '../../src/types';

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
  created_at: '2026-07-31T10:00:00Z',
};

function trendsBody(windowDays: number): TrendsResponse {
  return {
    window_days: windowDays,
    checkup_count: 3,
    alert_count: 1,
    markers: {
      glucose: {
        key: 'glucose',
        name: 'Salivary Glucose',
        unit: 'mg/dL',
        ref_low: 0.5,
        ref_high: 7.0,
        points: [
          {
            date: '2026-08-01T08:00:00Z',
            value: 2.1,
            state: 'normal',
            confidence: 0.9,
            name: 'Salivary Glucose',
            unit: 'mg/dL',
          },
          {
            date: '2026-08-05T08:00:00Z',
            value: 2.4,
            state: 'normal',
            confidence: 0.9,
            name: 'Salivary Glucose',
            unit: 'mg/dL',
          },
          {
            date: '2026-08-10T08:00:00Z',
            value: 2.8,
            state: 'normal',
            confidence: 0.9,
            name: 'Salivary Glucose',
            unit: 'mg/dL',
          },
        ],
        stats: { count: 3, mean: 2.43, std: 0.35, min: 2.1, max: 2.8, latest: 2.8 },
        alerts: [
          {
            type: 'rising_trend',
            severity: 'warning',
            message:
              'Salivary Glucose has risen over the last 3 checkups (2.10 → 2.80 mg/dL). Worth keeping an eye on.',
          },
        ],
      },
      crp: {
        key: 'crp',
        name: 'Salivary CRP',
        unit: 'ng/mL',
        ref_low: 0.02,
        ref_high: 1.5,
        points: [],
        stats: null,
        alerts: [],
      },
      cortisol: {
        key: 'cortisol',
        name: 'Salivary Cortisol',
        unit: 'µg/dL',
        ref_low: 0.1,
        ref_high: 0.6,
        points: [],
        stats: null,
        alerts: [],
      },
      ph: {
        key: 'ph',
        name: 'Salivary pH',
        unit: 'pH',
        ref_low: 6.5,
        ref_high: 7.4,
        points: [],
        stats: null,
        alerts: [],
      },
      siga: {
        key: 'siga',
        name: 'Secretory IgA',
        unit: 'mg/dL',
        ref_low: 5.0,
        ref_high: 25.0,
        points: [],
        stats: null,
        alerts: [],
      },
    },
  };
}

function AuthedHarness({ children }: { children: React.ReactNode }) {
  const { login } = useUserContext();
  useEffect(() => {
    login('token-abc', mockUser);
  }, [login]);
  return <>{children}</>;
}

function renderTrends() {
  localStorage.setItem('doctordrobe_token', 'token-abc');
  return render(
    <UserProvider>
      <MemoryRouter initialEntries={['/trends']}>
        <AuthedHarness>
          <Trends />
        </AuthedHarness>
      </MemoryRouter>
    </UserProvider>,
  );
}

describe('Trends', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/api/auth/me')) {
        return new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/trends')) {
        const windowDays = Number(new URL(url, API).searchParams.get('window_days'));
        return new Response(JSON.stringify(trendsBody(windowDays)), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      throw new Error(`Unexpected fetch call: ${url}`);
    });
  });

  it('renders marker charts and alerts', async () => {
    renderTrends();
    expect(await screen.findByTestId('trend-chart-glucose')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Salivary Glucose' }),
    ).toBeInTheDocument();
    expect(await screen.findByTestId('trend-alert-glucose')).toHaveTextContent(
      /risen over the last 3 checkups/i,
    );
    expect(screen.getByText('Checkups in window')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('shows an empty state when there are no checkups', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/api/auth/me')) {
        return new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/trends')) {
        const empty: TrendsResponse = {
          window_days: 30,
          checkup_count: 0,
          alert_count: 0,
          markers: Object.fromEntries(
            Object.entries(trendsBody(30).markers).map(([key, marker]) => [
              key,
              { ...marker, points: [], stats: null, alerts: [] },
            ]),
          ),
        };
        return new Response(JSON.stringify(empty), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      throw new Error(`Unexpected fetch call: ${url}`);
    });

    renderTrends();
    expect(await screen.findByText(/No checkups yet/i)).toBeInTheDocument();
  });

  it('switches the window and refetches', async () => {
    const user = userEvent.setup();
    renderTrends();
    await screen.findByTestId('trend-chart-glucose');

    await user.click(screen.getByTestId('trends-window-90'));
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/trends?window_days=90'),
        expect.anything(),
      );
    });
  });
});
