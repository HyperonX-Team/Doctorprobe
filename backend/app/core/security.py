"""Security helpers: device API key verification.

The device API key is enforced as a FastAPI dependency on the
device-reading endpoint. It can be promoted to global middleware by
registering ``DeviceAPIKeyMiddleware`` on the app — the dependency is
the recommended approach because it keeps the check explicit and testable.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def verify_device_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Require a valid `X-API-Key` header when `DEVICE_API_KEY` is configured.

    When ``DEVICE_API_KEY`` is unset (local development) the check is
    skipped so the ESP32 simulator can post readings without secrets.
    Comparison is constant-time to avoid timing attacks.
    """
    settings = get_settings()
    if not settings.DEVICE_API_KEY:
        return

    if x_api_key is None or not hmac.compare_digest(
        x_api_key, settings.DEVICE_API_KEY
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


# Middleware alternative — pluggable in `main.py` by adding to
# `app.add_middleware(DeviceAPIKeyMiddleware)` instead of the dependency.
# class DeviceAPIKeyMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request, call_next):
#         settings = get_settings()
#         if request.url.path == "/api/devices/reading" and settings.DEVICE_API_KEY:
#             key = request.headers.get("X-API-Key")
#             if key is None or not hmac.compare_digest(key, settings.DEVICE_API_KEY):
#                 return JSONResponse(
#                     {"detail": "Invalid or missing API key"},
#                     status_code=status.HTTP_401_UNAUTHORIZED,
#                 )
#         return await call_next(request)
