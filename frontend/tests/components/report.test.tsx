// Report page tests: report rendering, quality banner, PDF export button.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect } from 'react';
import Report from '../../src/pages/Report';
import { UserProvider, useUserContext } from '../../src/context/UserContext';
import { ToastProvider } from '../../src/components/ui/Toast';
import type { Checkup, User } from '../../src/types';

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

function makeCheckup(quality: Checkup['quality']): Checkup {
  return {
    id: 'checkup-1',
    user_id: mockUser.id,
    summary: 'Device reading · Overall risk LOW',
    overall_risk: 'low',
    quality_grade: quality?.grade ?? 'good',
    created_at: '2026-08-01T08:00:00Z',
    is_shared: false,
    text_summary: 'All markers are within their reference ranges.',
    biomarkers: [
      {
        key: 'glucose',
        name: 'Salivary Glucose',
        value: 4.2,
        unit: 'mg/dL',
        ref_low: 0.5,
        ref_high: 7.0,
        state: 'normal',
        message: 'Within range.',
        confidence: 0.9,
      },
    ],
    analysis: { method: 'spectral_nnls', prior_source: 'salinet', n_measurements: 3 },
    quality,
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function AuthedHarness({ children }: { children: React.ReactNode }) {
  const { login } = useUserContext();
  useEffect(() => {
    login('token-abc', mockUser);
  }, [login]);
  return <>{children}</>;
}

function renderReport(checkup: Checkup) {
  localStorage.setItem('doctordrobe_token', 'token-abc');
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes('/api/auth/me')) {
      return json(mockUser);
    }
    if (url.includes(`/api/checkups/${checkup.id}/export`)) {
      return new Response(new Blob(['%PDF-1.4 test'], { type: 'application/pdf' }));
    }
    if (url.includes(`/api/checkups/${checkup.id}`)) {
      return json(checkup);
    }
    throw new Error(`Unexpected fetch call: ${url}`);
  });
  return render(
    <UserProvider>
      <ToastProvider>
        <MemoryRouter initialEntries={['/report/checkup-1']}>
          <Routes>
            <Route
              path="/report/:checkupId"
              element={
                <AuthedHarness>
                  <Report />
                </AuthedHarness>
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </UserProvider>,
  );
}

describe('Report', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the report summary and biomarkers', async () => {
    renderReport(makeCheckup(undefined));
    expect(
      await screen.findByText(/All markers are within their reference ranges/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId('report-table')).toBeInTheDocument();
    expect(screen.getByText('Salivary Glucose')).toBeInTheDocument();
  });

  it('shows a retake banner for a poor-quality reading', async () => {
    renderReport(
      makeCheckup({
        grade: 'poor',
        reasons: ['Readings vary between snapshots (rgb_r variation 25%)'],
        recommended_action: 'retake_reading',
      }),
    );
    expect(await screen.findByTestId('report-quality')).toHaveTextContent(
      /may not be trustworthy/i,
    );
    expect(screen.getByTestId('report-quality')).toHaveTextContent(
      /retake the reading/i,
    );
  });

  it('does not show a banner for a good reading', async () => {
    renderReport(makeCheckup({ grade: 'good', reasons: [], recommended_action: null }));
    await screen.findByText('Salivary Glucose');
    expect(screen.queryByTestId('report-quality')).not.toBeInTheDocument();
  });

  it('downloads the clinician PDF from the export endpoint', async () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:mock-report-pdf');
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL,
      revokeObjectURL: vi.fn(),
    });

    const user = userEvent.setup();
    renderReport(makeCheckup(undefined));
    await screen.findByText('Salivary Glucose');

    await user.click(screen.getByTestId('report-export-pdf'));

    await waitFor(() => {
      const calls = vi
        .mocked(globalThis.fetch)
        .mock.calls.map(([input]) => String(input));
      expect(calls.some((url) => url.includes('/api/checkups/checkup-1/export'))).toBe(
        true,
      );
    });
  });
});
