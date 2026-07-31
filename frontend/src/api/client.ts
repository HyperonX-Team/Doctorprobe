// Typed fetch client for the Doctordrobe REST API.
// - All endpoints return typed promises.
// - Non-2xx responses throw ApiError with the backend's `detail` message.
// - 2xx-with-body responses are parsed as JSON.

import { API_BASE_URL, ENDPOINTS } from './endpoints';
import type {
  Checkup,
  CheckupCreate,
  CheckupCreated,
  CheckupSummary,
  DeviceReading,
  DeviceStatus,
  ShareResponse,
  User,
  UserCreate,
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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  };

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
  /** POST /api/users */
  createUser: (payload: UserCreate) =>
    request<User>(ENDPOINTS.userCreate, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** GET /api/users/{id} */
  getUser: (userId: string) => request<User>(ENDPOINTS.user(userId)),

  /** PUT /api/users/{id} */
  updateUser: (userId: string, payload: UserUpdate) =>
    request<User>(ENDPOINTS.user(userId), {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  /** DELETE /api/users/{id} */
  deleteUser: (userId: string) =>
    request<{ detail: string }>(ENDPOINTS.user(userId), { method: 'DELETE' }),

  /** GET /api/users/{id}/checkups */
  listCheckups: (userId: string) =>
    request<CheckupSummary[]>(ENDPOINTS.userCheckups(userId)),

  /** POST /api/checkups */
  createCheckup: (payload: CheckupCreate) =>
    request<CheckupCreated>(ENDPOINTS.checkupCreate, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** GET /api/checkups/{id}?user_id=... */
  getCheckup: (checkupId: string, userId: string) =>
    request<Checkup>(
      `${ENDPOINTS.checkup(checkupId)}?user_id=${encodeURIComponent(userId)}`,
    ),

  /** DELETE /api/checkups/{id} (body carries user_id) */
  deleteCheckup: (checkupId: string, userId: string) =>
    request<{ detail: string }>(ENDPOINTS.checkup(checkupId), {
      method: 'DELETE',
      body: JSON.stringify({ user_id: userId }),
    }),

  /** POST /api/checkups/{id}/share */
  shareCheckup: (checkupId: string, userId: string) =>
    request<ShareResponse>(ENDPOINTS.checkupShare(checkupId), {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }),

  /** GET /api/devices/latest?device_id=... */
  getLatestReading: (deviceId: string) =>
    request<DeviceReading>(ENDPOINTS.deviceLatest(deviceId)),

  /** GET /api/devices/status?device_id=... */
  getDeviceStatus: (deviceId: string) =>
    request<DeviceStatus>(ENDPOINTS.deviceStatus(deviceId)),
};

export { API_BASE_URL };
