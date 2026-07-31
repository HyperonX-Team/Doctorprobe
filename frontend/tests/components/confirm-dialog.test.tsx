// ConfirmDialog component tests: open state, confirm/cancel callbacks,
// busy state, and backdrop click.

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ConfirmDialog from '../../src/components/ui/ConfirmDialog';

describe('ConfirmDialog', () => {
  it('renders nothing when closed', () => {
    render(
      <ConfirmDialog
        open={false}
        title="Delete?"
        message="Really?"
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />,
    );
    expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
  });

  it('shows title, message and buttons when open', () => {
    render(
      <ConfirmDialog
        open
        title="Delete checkup?"
        message="This cannot be undone."
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />,
    );
    expect(screen.getByRole('dialog')).toHaveAccessibleName('Delete checkup?');
    expect(screen.getByText('This cannot be undone.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  it('calls onConfirm when the confirm button is clicked', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Delete?"
        message="Really?"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );

    await user.click(screen.getByTestId('confirm-action'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('calls onCancel when cancelled and when the backdrop is clicked', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Delete?"
        message="Really?"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );

    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);

    await user.click(screen.getByTestId('confirm-dialog'));
    expect(onCancel).toHaveBeenCalledTimes(2);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('disables buttons while busy', () => {
    render(
      <ConfirmDialog
        open
        busy
        title="Delete?"
        message="Really?"
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />,
    );
    expect(screen.getByTestId('confirm-action')).toBeDisabled();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
    expect(screen.getByTestId('confirm-action')).toHaveTextContent('Working…');
  });
});
