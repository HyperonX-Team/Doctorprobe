// Error helpers for consistent user-facing messages.

import { ApiError } from '../api/client';

/**
 * Convert any thrown value into a readable message.
 * ApiError carries the backend `detail`; everything else gets a generic
 * fallback so the UI never shows "undefined".
 */
export function getErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    return err.message;
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return 'Something went wrong. Please try again.';
}
