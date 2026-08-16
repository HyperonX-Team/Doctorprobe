// History page tests: pagination (load more + total), quality badge.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import History from '../../src/pages/History';
import { UserProvider } from '../../src/context/UserContext';
import { ToastProvider } from '../../src/components/ui/Toast';
import type { CheckupSummary, User } from '../../src/types';

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

function makeCheckups(count: number, offset = 0): CheckupSummary[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `checkup-${offset + index + 1}`,
    user_id: mockUser.id,
    summary: `Device reading · Overall risk LOW · 0 marker(s) out of range`,
    overall_risk: 'low' as const,
    quality_grade: index % 2 === 0 ? 'good' : 'poor',
    created_at: `2026-08-${String((index % 28) + 1).padStart(2, '0')}T08:00:00Z`,
    is_shared: false,
  }));
}

function renderHistory() {
  // The token is set up front so the UserProvider hydrates the session
  // from GET /api/auth/me (no double login/re-render race).
  localStorage.setItem('doctordrobe_token', 'token-abc');
  return render(
    <UserProvider>
      <ToastProvider>
        <MemoryRouter initialEntries={['/history']}>
          <History />
        </MemoryRouter>
      </ToastProvider>
    </UserProvider>,
  );
}

describe('History', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/api/auth/me/checkups')) {
        const parsed = new URL(url, 'http://localhost:8000');
        const limit = Number(parsed.searchParams.get('limit') ?? 20);
        const offset = Number(parsed.searchParams.get('offset') ?? 0);
        const all = makeCheckups(25);
        const page = all.slice(offset, offset + limit);
        return new Response(JSON.stringify(page), {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
            'X-Total-Count': '25',
          },
        });
      }
      if (url.includes('/api/auth/me')) {
        return new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      throw new Error(`Unexpected fetch call: ${url}`);
    });
  });

  it('renders the total count and quality badges', async () => {
    renderHistory();
    expect(await screen.findByTestId('history-total')).toHaveTextContent('25 checkups total');
    const rows = await screen.findAllByTestId('history-row');
    expect(rows.length).toBeGreaterThan(0);
    expect(screen.getAllByText('POOR').length).toBeGreaterThan(0);
  });

  it('loads more pages via the pager', async () => {
    const user = userEvent.setup();
    renderHistory();
    await screen.findByTestId('history-total');

    await user.click(screen.getByTestId('history-load-more'));

    await waitFor(() => {
      const calls = vi
        .mocked(globalThis.fetch)
        .mock.calls.map(([input]) => String(input));
      expect(calls.some((url) => url.includes('offset=20'))).toBe(true);
    });
  });
});
