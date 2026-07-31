// API path constants. The base URL comes from the Vite environment:
//   .env.development -> http://localhost:8000
//   .env.production  -> /api (Nginx proxy)
// No hardcoded secrets live in this file.

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000';

export const ENDPOINTS = {
  health: '/health',
  userCreate: '/api/users',
  user: (userId: string) => `/api/users/${userId}`,
  userCheckups: (userId: string) => `/api/users/${userId}/checkups`,
  checkupCreate: '/api/checkups',
  checkup: (checkupId: string) => `/api/checkups/${checkupId}`,
  checkupShare: (checkupId: string) => `/api/checkups/${checkupId}/share`,
  deviceLatest: (deviceId: string) =>
    `/api/devices/latest?device_id=${encodeURIComponent(deviceId)}`,
  deviceStatus: (deviceId: string) =>
    `/api/devices/status?device_id=${encodeURIComponent(deviceId)}`,
} as const;
