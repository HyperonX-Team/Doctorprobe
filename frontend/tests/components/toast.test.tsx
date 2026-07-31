// Toast component tests: success rendering, auto-dismiss, manual dismiss.

import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ToastProvider, useToast } from '../../src/components/ui/Toast';

function ToastDemo({ message = 'Hello world' }: { message?: string }) {
  const { show } = useToast();
  return (
    <button type="button" onClick={() => show(message, 'success')}>
      Trigger
    </button>
  );
}

function renderToast() {
  return render(
    <ToastProvider>
      <ToastDemo />
    </ToastProvider>,
  );
}

describe('Toast', () => {
  it('renders a toast when triggered', async () => {
    const user = userEvent.setup();
    renderToast();

    await user.click(screen.getByText('Trigger'));
    expect(await screen.findByRole('status')).toHaveTextContent('Hello world');
  });

  it('auto-dismisses after the timeout', () => {
    vi.useFakeTimers();
    renderToast();

    // fireEvent is synchronous and timer-free, safe under fake timers.
    fireEvent.click(screen.getByText('Trigger'));
    expect(screen.getByRole('status')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it('dismisses manually via the close button', async () => {
    const user = userEvent.setup();
    renderToast();

    await user.click(screen.getByText('Trigger'));
    const toast = await screen.findByRole('status');
    await user.click(screen.getByLabelText('Dismiss notification'));

    expect(toast).not.toBeInTheDocument();
  });
});
