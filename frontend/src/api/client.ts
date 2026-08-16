// Typed fetch client for the Doctordrobe REST API.
// - All endpoints return typed promises.
// - Non-2xx responses throw ApiError with the backend's `detail` message.
// - 2xx-with-body responses are parsed as JSON.
// - Authenticated requests carry the bearer token (from register/login)
//   in the Authorization header; the owning user is derived from it.

import { API_BASE_URL, ENDPOINTS } from './endpoints';
import type {
  AuthResponse,
  CalibrationStats,
  ChangePasswordInput,
  Checkup,
  CheckupCreated,
  CheckupSummary,
  CommunityInsights,
  DeviceBaseline,
  DeviceReading,
  DeviceStatus,
  LoginInput,
  NotificationsResponse,
  RegisterInput,
  ShareResponse,
  TrendsResponse,
  User,
  UserUpdate,
} from '../types';

/** Error thrown for any non-ok API response. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

interface ErrorEnvelope {
  detail?: string;
}

const TOKEN_KEY = 'doctordrobe_token';

/**
 * Dispatched when an authenticated request comes back 401 — i.e. the
 * session expired or was revoked server-side. The UserContext listens
 * for it and signs the user out instead of showing a stale error.
 */
export const UNAUTHORIZED_EVENT = 'doctordrobe:unauthorized';

/** Store (or clear) the session bearer token. */
export function setAuthToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    // Network-level failure (backend unreachable, CORS, DNS, ...).
    throw new ApiError(
      0,
      'Cannot reach the Doctordrobe server. Is the backend running?',
    );
  }

  if (!response.ok) {
    // A 401 while holding a session token means the session is gone
    // (expired, password changed elsewhere, account deleted). Surface it
    // so the app can sign the user out cleanly. Login failures are not
    // affected because no token is stored yet at that point.
    if (response.status === 401 && localStorage.getItem(TOKEN_KEY)) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    let message = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as ErrorEnvelope;
      if (typeof body.detail === 'string' && body.detail) {
        message = body.detail;
      }
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(response.status, message);
  }

  // 204 No Content and empty bodies.
  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  /** POST /api/auth/register — creates the account and starts a session. */
  register: (payload: RegisterInput) =>
    request<AuthResponse>(ENDPOINTS.authRegister, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** POST /api/auth/login */
  login: (payload: LoginInput) =>
    request<AuthResponse>(ENDPOINTS.authLogin, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** POST /api/auth/logout — revokes the current session server-side. */
  logout: () => request<{ detail: string }>(ENDPOINTS.authLogout, { method: 'POST' }),

  /** GET /api/auth/me */
  getMe: () => request<User>(ENDPOINTS.authMe),

  /** PUT /api/auth/me */
  updateMe: (payload: UserUpdate) =>
    request<User>(ENDPOINTS.authMe, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  /** DELETE /api/auth/me — deletes the account and all checkups. */
  deleteMe: () => request<{ detail: string }>(ENDPOINTS.authMe, { method: 'DELETE' }),

  /** POST /api/auth/change-password — revokes every other session. */
  changePassword: (payload: ChangePasswordInput) =>
    request<{ detail: string }>(ENDPOINTS.authChangePassword, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** GET /api/auth/me/checkups — summaries, newest first. */
  listCheckups: () => request<CheckupSummary[]>(ENDPOINTS.authMyCheckups),

  /** GET /api/auth/me/checkups?limit=&offset= — paged list with total. */
  listCheckupsPage: async (
    limit = 20,
    offset = 0,
  ): Promise<{ items: CheckupSummary[]; total: number }> => {
    const { data, headers } = await requestWithMeta<CheckupSummary[]>(
      `${ENDPOINTS.authMyCheckups}?limit=${limit}&offset=${offset}`,
    );
    const total = Number(headers.get('x-total-count') ?? data.length);
    return { items: data, total: Number.isFinite(total) ? total : data.length };
  },

  /** GET /api/auth/me/export — full personal data as a JSON download. */
  exportMe: () => fetchBlob(ENDPOINTS.authMeExport),

  /** PUT /api/checkups/{id}/note — set or clear the report note. */
  updateCheckupNote: (checkupId: string, note: string) =>
    request<Checkup>(ENDPOINTS.checkupNote(checkupId), {
      method: 'PUT',
      body: JSON.stringify({ note }),
    }),

  /** GET /api/trends/export?window_days= — trends series as CSV. */
  exportTrends: (windowDays = 30) => fetchBlob(ENDPOINTS.trendsExport(windowDays)),

  /** GET /api/shares/insights — anonymized community cohort aggregates. */
  getCommunityInsights: () => request<CommunityInsights>(ENDPOINTS.sharesInsights),

  /** GET /api/notifications — in-app notifications + unread count. */
  getNotifications: () => request<NotificationsResponse>(ENDPOINTS.notifications),

  /** POST /api/notifications/read — mark all notifications read. */
  markNotificationsRead: () =>
    request<NotificationsResponse>(ENDPOINTS.notificationsRead, { method: 'POST' }),

  /** GET /api/devices/baseline?device_id= — stored blank-pad baseline. */
  getDeviceBaseline: (deviceId: string) =>
    request<DeviceBaseline>(ENDPOINTS.deviceBaseline(deviceId)),

  /** POST /api/checkups — analyzes the authenticated user's latest reading. */
  createCheckup: () =>
    request<CheckupCreated>(ENDPOINTS.checkupCreate, { method: 'POST' }),

  /** GET /api/checkups/{id} */
  getCheckup: (checkupId: string) => request<Checkup>(ENDPOINTS.checkup(checkupId)),

  /** DELETE /api/checkups/{id} */
  deleteCheckup: (checkupId: string) =>
    request<{ detail: string }>(ENDPOINTS.checkup(checkupId), { method: 'DELETE' }),

  /** POST /api/checkups/{id}/share */
  shareCheckup: (checkupId: string) =>
    request<ShareResponse>(ENDPOINTS.checkupShare(checkupId), { method: 'POST' }),

  /** GET /api/checkups/{id}/export — clinician PDF, returned as a blob. */
  exportCheckup: (checkupId: string) => fetchBlob(ENDPOINTS.checkupExport(checkupId)),

  /** GET /api/calibration/export — trainer CSV, returned as a blob. */
  exportCalibrationCsv: () => fetchBlob(ENDPOINTS.calibrationExport),

  /** GET /api/calibration/stats */
  getCalibrationStats: () => request<CalibrationStats>(ENDPOINTS.calibrationStats),

  /** DELETE /api/calibration/samples — clear all labeled samples. */
  clearCalibrationSamples: () =>
    request<{ detail: string }>(ENDPOINTS.calibrationSamples, { method: 'DELETE' }),

  /** GET /api/trends?window_days=... */
  getTrends: (windowDays = 30) => request<TrendsResponse>(ENDPOINTS.trends(windowDays)),

  /** GET /api/devices/latest?device_id=... */
  getLatestReading: (deviceId: string) =>
    request<DeviceReading>(ENDPOINTS.deviceLatest(deviceId)),

  /** GET /api/devices/status?device_id=... */
  getDeviceStatus: (deviceId: string) =>
    request<DeviceStatus>(ENDPOINTS.deviceStatus(deviceId)),
};

export { API_BASE_URL };

/** Like request(), but also returns the raw headers (for pagination). */
async function requestWithMeta<T>(
  path: string,
  init: RequestInit = {},
): Promise<{ data: T; headers: Headers }> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      0,
      'Cannot reach the Doctordrobe server. Is the backend running?',
    );
  }

  if (!response.ok) {
    if (response.status === 401 && localStorage.getItem(TOKEN_KEY)) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    let message = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as ErrorEnvelope;
      if (typeof body.detail === 'string' && body.detail) {
        message = body.detail;
      }
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(response.status, message);
  }
  return { data: (await response.json()) as T, headers: response.headers };
}

/** Fetch a path as a raw blob with the bearer token attached. */
async function fetchBlob(path: string): Promise<Blob> {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { headers });
  } catch {
    throw new ApiError(
      0,
      'Cannot reach the Doctordrobe server. Is the backend running?',
    );
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as ErrorEnvelope;
      if (typeof body.detail === 'string' && body.detail) {
        message = body.detail;
      }
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(response.status, message);
  }
  return response.blob();
}
