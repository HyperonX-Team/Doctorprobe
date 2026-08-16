// Community Insights page tests: cohort stats, marker comparison, empty state.

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect } from 'react';
import Community from '../../src/pages/Community';
import { UserProvider, useUserContext } from '../../src/context/UserContext';
import type { CommunityInsights, User } from '../../src/types';

const mockUser: User = {
  id: 'user-123',
  email: 'tester@example.com',
  age: 34,
  sex: 'female',
  height_cm: 165,
  weight_kg: 62,
  activity_level: 'moderate',
  share_data: true,
  token_balance: 10,
  device_id: 'doctordrobe_demo_001',
  reference_ranges: null,
  created_at: '2026-07-31T10:00:00Z',
};

function insightsBody(): CommunityInsights {
  return {
    cohort_checkups: 4,
    cohort_users: 2,
    min_cohort: 3,
    similar_profile: { sex: 'female', age_band: '29-39', activity_level: 'moderate' },
    similar_profile_count: 2,
    markers: {
      glucose: {
        key: 'glucose',
        name: 'Salivary Glucose',
        unit: 'mg/dL',
        user_latest: 4.2,
        user_state: 'normal',
        cohort_count: 4,
        cohort_mean: 3.1,
        cohort_std: 0.8,
        cohort_p10: 2.1,
        cohort_p50: 3.2,
        cohort_p90: 4.0,
        user_percentile: 0.88,
        ref_low: 0.5,
        ref_high: 7.0,
      },
      crp: {
        key: 'crp',
        name: 'Salivary CRP',
        unit: 'ng/mL',
        user_latest: 0.4,
        user_state: 'normal',
        cohort_count: 0,
        cohort_mean: null,
        cohort_std: null,
        cohort_p10: null,
        cohort_p50: null,
        cohort_p90: null,
        user_percentile: null,
        ref_low: 0.02,
        ref_high: 1.5,
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

function renderCommunity() {
  localStorage.setItem('doctordrobe_token', 'token-abc');
  return render(
    <UserProvider>
      <MemoryRouter initialEntries={['/community']}>
        <AuthedHarness>
          <Community />
        </AuthedHarness>
      </MemoryRouter>
    </UserProvider>,
  );
}

describe('Community', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/api/auth/me')) {
        return new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/shares/insights')) {
        return new Response(JSON.stringify(insightsBody()), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      throw new Error(`Unexpected fetch call: ${url}`);
    });
  });

  it('renders cohort stats and the you-vs-community comparison', async () => {
    renderCommunity();
    expect(await screen.findByTestId('community-cohort-checkups')).toHaveTextContent('4');
    expect(screen.getByTestId('community-marker-glucose')).toBeInTheDocument();
    expect(screen.getByTestId('community-percentile-glucose')).toHaveTextContent(
      /in line with ~88% of similar profiles/i,
    );
    expect(screen.getByText(/Community median/)).toBeInTheDocument();
  });

  it('shows an honest empty state for markers without cohort data', async () => {
    renderCommunity();
    await screen.findByTestId('community-marker-glucose');
    expect(screen.getByTestId('community-marker-crp')).toHaveTextContent(
      /No community data for this marker yet/i,
    );
  });
});
