// API path constants. The base URL comes from the Vite environment:
//   .env.development -> http://localhost:8000
//   .env.production  -> /api (Nginx proxy)
// No hardcoded secrets live in this file.

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000';

export const ENDPOINTS = {
  health: '/health',
  authRegister: '/api/auth/register',
  authLogin: '/api/auth/login',
  authLogout: '/api/auth/logout',
  authMe: '/api/auth/me',
  authChangePassword: '/api/auth/change-password',
  authMyCheckups: '/api/auth/me/checkups',
  authMeExport: '/api/auth/me/export',
  checkupCreate: '/api/checkups',
  checkup: (checkupId: string) => `/api/checkups/${checkupId}`,
  checkupExport: (checkupId: string) => `/api/checkups/${checkupId}/export`,
  checkupShare: (checkupId: string) => `/api/checkups/${checkupId}/share`,
  checkupNote: (checkupId: string) => `/api/checkups/${checkupId}/note`,
  trends: (windowDays: number) => `/api/trends?window_days=${windowDays}`,
  trendsExport: (windowDays: number) => `/api/trends/export?window_days=${windowDays}`,
  sharesInsights: '/api/shares/insights',
  notifications: '/api/notifications',
  notificationsRead: '/api/notifications/read',
  calibrationStats: '/api/calibration/stats',
  calibrationExport: '/api/calibration/export',
  calibrationSamples: '/api/calibration/samples',
  deviceLatest: (deviceId: string) =>
    `/api/devices/latest?device_id=${encodeURIComponent(deviceId)}`,
  deviceStatus: (deviceId: string) =>
    `/api/devices/status?device_id=${encodeURIComponent(deviceId)}`,
  deviceBaseline: (deviceId: string) =>
    `/api/devices/baseline?device_id=${encodeURIComponent(deviceId)}`,
} as const;
