// Calibration page tests: coverage rendering, threshold badge, export.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect } from 'react';
import Calibration from '../../src/pages/Calibration';
import { UserProvider, useUserContext } from '../../src/context/UserContext';
import { ToastProvider } from '../../src/components/ui/Toast';
import type { CalibrationStats, User } from '../../src/types';

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

const stats: CalibrationStats = {
  total_samples: 17,
  min_real_samples: 15,
  analytes: {
    glucose: {
      name: 'Salivary Glucose',
      unit: 'mg/dL',
      count: 15,
      min_concentration: 0.5,
      max_concentration: 4.0,
      envelope_min: 0.05,
      envelope_max: 50.0,
      enough: true,
      last_sample_at: '2026-08-10T08:00:00Z',
      model_source: 'real',
      model_metrics: { r2: 0.81, mae: 0.4 },
    },
    crp: {
      name: 'Salivary CRP',
      unit: 'ng/mL',
      count: 2,
      min_concentration: 0.1,
      max_concentration: 0.4,
      envelope_min: 0.005,
      envelope_max: 20.0,
      enough: false,
      last_sample_at: '2026-08-11T08:00:00Z',
      model_source: 'synthetic',
      model_metrics: { r2: 0.92, mae: 0.07 },
    },
    cortisol: {
      name: 'Salivary Cortisol',
      unit: 'µg/dL',
      count: 0,
      min_concentration: null,
      max_concentration: null,
      envelope_min: 0.005,
      envelope_max: 5.0,
      enough: false,
      last_sample_at: null,
      model_source: 'synthetic',
      model_metrics: { r2: 0.89, mae: 0.05 },
    },
    siga: {
      name: 'Secretory IgA',
      unit: 'mg/dL',
      count: 0,
      min_concentration: null,
      max_concentration: null,
      envelope_min: 0.5,
      envelope_max: 200.0,
      enough: false,
      last_sample_at: null,
      model_source: 'synthetic',
      model_metrics: { r2: 0.56, mae: 2.37 },
    },
  },
  model: {
    present: true,
    model_name: 'SaliNet',
    model_version: '2.0.0',
    trained_at: '2026-07-31T23:17:18+00:00',
  },
};

function AuthedHarness({ children }: { children: React.ReactNode }) {
  const { login } = useUserContext();
  useEffect(() => {
    login('token-abc', mockUser);
  }, [login]);
  return <>{children}</>;
}

function renderCalibration() {
  localStorage.setItem('doctordrobe_token', 'token-abc');
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes('/api/auth/me')) {
      return new Response(JSON.stringify(mockUser), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    if (url.includes('/api/calibration/stats')) {
      return new Response(JSON.stringify(stats), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    if (url.includes('/api/calibration/export')) {
      return new Response(new Blob(['rgb_r,rgb_g\n1,2\n'], { type: 'text/csv' }));
    }
    throw new Error(`Unexpected fetch call: ${url}`);
  });
  return render(
    <UserProvider>
      <ToastProvider>
        <MemoryRouter initialEntries={['/calibration']}>
          <AuthedHarness>
            <Calibration />
          </AuthedHarness>
        </MemoryRouter>
      </ToastProvider>
    </UserProvider>,
  );
}

describe('Calibration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders per-analyte coverage and the enough badge', async () => {
    renderCalibration();
    expect(
      await screen.findByTestId('calibration-analyte-glucose'),
    ).toBeInTheDocument();
    expect(screen.getByTestId('calibration-enough-glucose')).toHaveTextContent(
      'Ready to train',
    );
    expect(screen.getByTestId('calibration-enough-crp')).toHaveTextContent(
      'Keep collecting',
    );
    expect(screen.getByTestId('calibration-total')).toHaveTextContent('17');
  });

  it('shows the deployed model version', async () => {
    renderCalibration();
    expect(await screen.findByTestId('calibration-model-version')).toHaveTextContent(
      '2.0.0',
    );
  });

  it('exports the training CSV from the export endpoint', async () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:mock-calibration-csv');
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL: vi.fn() });

    const user = userEvent.setup();
    renderCalibration();
    await user.click(await screen.findByTestId('calibration-export'));

    await waitFor(() => {
      const calls = vi
        .mocked(globalThis.fetch)
        .mock.calls.map(([input]) => String(input));
      expect(calls.some((url) => url.includes('/api/calibration/export'))).toBe(true);
    });
  });
});
