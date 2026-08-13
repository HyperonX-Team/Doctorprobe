# Doctordrobe

A home-health analyzer: an ESP32 sensor device, a FastAPI backend, and a
React SPA. Saliva strips are read by an RGB spectrometer; the backend
models the strip's chromogen colour with Beer–Lambert reflectance
chemistry into a panel of saliva-valid analytes (glucose, CRP, cortisol,
pH, secretory IgA), adjusts for the user profile, encrypts the report at
rest with Fernet, and presents it in a chat-style UI. Every checkup is
derived from a real device reading.

> **Not a medical device.** SaliNet (the sensor model) is trained on
> synthetic data until you collect real calibration samples with the
> firmware's calibration mode — see the [Calibration protocol](#calibration-protocol)
> below.

## Architecture

```
┌────────────────────────┐          HTTPS          ┌───────────────────────────┐
│ ESP32 (Arduino)        │  ─────────────────────► │ FastAPI backend           │
│  TCS34725 RGB sensor   │   POST /api/devices/    │  /api/auth               │
│  DHT22 temp/humidity   │   reading               │  /api/checkups           │
│  Button + status LED   │                         │  /api/devices            │
│  ArduinoJson over HTTP │                         │  /api/trends             │
└────────────────────────┘                         └─────────────┬─────────────┘
                                                                 │ SQLAlchemy 2.0
                                                                 │ (async ORM)
                                                                 ▼
                                                ┌──────────────────────────────┐
                                                │ PostgreSQL 16 (prod)         │
                                                │ SQLite (dev)                 │
                                                │ Alembic migrations           │
                                                └──────────────────────────────┘

┌──────────────────────────┐   HTTPS   ┌───────────────────────────────┐
│ Browser / React 18 SPA   │ ────────► │ Nginx (port 80)               │
│ (Vite, Tailwind 3.4)     │  /api/*   │  serves the static SPA        │
│                          │  proxy    │  proxies /api → backend:8000  │
└──────────────────────────┘           └───────────────┬───────────────┘
                                                       │ container network
                                                       ▼
                                        ┌───────────────────────────────┐
                                        │ FastAPI backend (port 8000)   │
                                        │ uvicorn                       │
                                        └───────────────────────────────┘
```

## Repository layout

| Path              | Contents                                        |
| ----------------- | ----------------------------------------------- |
| `backend/`        | FastAPI application, Alembic migrations, pytest |
| `frontend/`       | React SPA, Vitest + RTL, ESLint/Prettier        |
| `arduino/`        | ESP32 firmware (Arduino framework)              |
| `infra/`          | `docker-compose.yml`, Nginx config              |
| `.github/workflows/` | CI: tests + lint + image builds              |

## Quick start (Docker Compose)

```bash
cp .env.example .env      # then edit FERNET_KEY / DEVICE_API_KEY
docker compose -f infra/docker-compose.yml up --build
```

- Frontend: http://localhost
- Backend API + OpenAPI docs: http://localhost:8000/docs
- Health checks: `http://localhost/health`, `http://localhost:8000/health`

The backend runs Alembic migrations against PostgreSQL on startup, and
the Nginx container proxies `/api/*` to the backend.

## Local development (no Docker)

### Backend

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate      # Windows
source .venv/bin/activate                           # macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

`frontend/.env.development` points at `http://localhost:8000`; add
`http://localhost:5173` to `CORS_ORIGINS` in `backend/.env` if needed.

## Hardware setup

Full parts list, wiring diagram, and assembly steps:
[`arduino/doctordrobe/BUILD_GUIDE.md`](arduino/doctordrobe/BUILD_GUIDE.md)
(~$35–45 in parts). Firmware details:
[`arduino/doctordrobe/README.md`](arduino/doctordrobe/README.md).

| Part | ESP32 pin |
| ---- | --------- |
| TCS34725 | I2C: SDA → GPIO21, SCL → GPIO22 |
| DHT22 | DATA → GPIO4 |
| Button | GPIO0 ↔ GND (INPUT_PULLUP) |
| LED | GPIO2 |

1. Copy `config.h` values for your Wi-Fi and backend address.
2. `cp arduino/doctordrobe/secrets.h.example arduino/doctordrobe/secrets.h`
   and set `DEVICE_API_KEY` if the backend enforces one.
3. Flash with Arduino IDE 2.x (ESP32 core 2.0.14, libraries: Adafruit
   TCS34725, DHT sensor library, ArduinoJson ≥ 7).
4. Press the button — the device posts a reading; the LED blinks 3× on
   success. Then run a checkup in the app with **Scan with Device**.

## API

Base URL `/api`. All errors use `{"detail": "message"}`. Interactive
docs at `/docs` (Swagger UI).

### Auth

Identity is email + password. Register/login return an opaque bearer
token plus the profile; every other authenticated request carries it in
the `Authorization: Bearer` header, and the owning user is always derived
from that token — never from a client-supplied id. Tokens are stored
(hashed) in the `sessions` table, expire after `SESSION_TTL_DAYS`, and
can be revoked individually (logout) or in bulk (password change,
account deletion). Login is rate-limited per IP
(`AUTH_LOGIN_MAX_ATTEMPTS` / `AUTH_LOGIN_WINDOW_SECONDS`).

| Method | Path | Body / Query | Returns |
| ------ | ---- | ------------ | ------- |
| POST | `/api/auth/register` | `RegisterRequest` (profile + email + password) | `AuthResponse` (201) |
| POST | `/api/auth/login` | `LoginRequest` | `AuthResponse` |
| POST | `/api/auth/logout` | — | `{"detail": ...}` |
| GET | `/api/auth/me` | — | `UserResponse` |
| PUT | `/api/auth/me` | `UserUpdate` (partial) | `UserResponse` |
| DELETE | `/api/auth/me` | — | `{"detail": ...}` |
| POST | `/api/auth/change-password` | `ChangePasswordRequest` | `{"detail": ...}` |
| GET | `/api/auth/me/checkups` | — | `CheckupSummary[]` |

**Register**

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"correct-horse-9!","age":34,"sex":"female","height_cm":165,"weight_kg":62,"activity_level":"moderate"}'
```

```json
{
  "token": "Qw9pV...opaque-bearer-token...",
  "user": {
    "id": "274078c2-c56b-44c6-8785-6c1bb9ec472c",
    "email": "you@example.com",
    "age": 34,
    "sex": "female",
    "height_cm": 165.0,
    "weight_kg": 62.0,
    "activity_level": "moderate",
    "share_data": false,
    "token_balance": 0,
    "device_id": "doctordrobe_demo_001",
    "created_at": "2026-07-31T20:20:58Z"
  }
}
```

**Login** (subsequent requests send `Authorization: Bearer <token>`):

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"correct-horse-9!"}'

curl http://localhost:8000/api/auth/me -H "Authorization: Bearer $TOKEN"
```

### Checkups

All checkup endpoints require `Authorization: Bearer <token>`; the owning
user is resolved from the token.

| Method | Path | Body / Query | Returns |
| ------ | ---- | ------------ | ------- |
| POST | `/api/checkups` | — | `CheckupCreated` (201) |
| GET | `/api/checkups/{id}` | — | `CheckupResponse` (decrypted) |
| DELETE | `/api/checkups/{id}` | — | `{"detail": ...}` |
| POST | `/api/checkups/{id}/share` | — | `ShareResponse` |

`POST /api/checkups` derives the report from the user's latest device
reading and returns **409** when no reading exists yet. Sharing awards
`TOKEN_REWARD` (default 5) tokens once per checkup; a second share
returns **409**. Reading or sharing another user's checkup returns
**403**.

### Trends

| Method | Path | Query | Returns |
| ------ | ---- | ----- | ------- |
| GET | `/api/trends` | `?window_days=` (1–365, default 30) | per-marker series, stats, alerts |

`GET /api/trends` decrypts the authenticated user's own checkups and
returns, per marker: a time series (oldest→newest), window statistics,
and deterministic alerts — `rising_trend` / `falling_trend` (last three
values moving together), `deviation_from_baseline` (> 2 standard
deviations from the user's earlier readings), and
`repeated_out_of_range` / `new_out_of_range`. Alerts are conservative
heads-ups, never a diagnosis.

### Devices

| Method | Path | Query | Returns |
| ------ | ---- | ----- | ------- |
| POST | `/api/devices/reading` | — (requires `X-API-Key` when `DEVICE_API_KEY` set) | `DeviceReadingResponse` (201) |
| GET | `/api/devices/latest` | `?device_id=` | `DeviceReadingResponse` |
| GET | `/api/devices/status` | `?device_id=` | `{"connected", "last_seen"}` |

```bash
curl -X POST http://localhost:8000/api/devices/reading \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $DEVICE_API_KEY" \
  -d '{"device_id":"doctordrobe_demo_001","rgb_r":120,"rgb_g":200,"rgb_b":60,"temperature_c":24.5,"humidity_pct":45}'
```

### Report format

Reports are derived from a physical device reading via **SaliNet** — a
small multi-output Random Forest that inverts the strip's colorimetric
chemistry (Beer-Lambert reflectance + pad cross-talk + sensor noise,
simulated in `backend/scripts/generate_synthetic_data.py` and trained
by `backend/scripts/train_model.py`; held-out R² ≈ 0.56–0.76 per
analyte). The closed-form Beer-Lambert calibration is the fallback when
the model artifact is absent. The panel uses saliva-valid analytes with
literature-plausible ranges:

| Analyte | Signal | Unit | Reference range |
| ------- | ------ | ---- | --------------- |
| Salivary Glucose | red pad | mg/dL | 0.5 – 7.0 |
| Salivary CRP | blue pad | ng/mL | 0.02 – 1.5 |
| Salivary Cortisol | green pad | µg/dL | 0.1 – 0.6 (morning) |
| Salivary pH | blue/green ratio | pH | 6.5 – 7.4 |
| Secretory IgA | total intensity (turbidimetric) | mg/dL | 5.0 – 25.0 |

```json
{
  "overall_risk": "low",
  "text_summary": "Analysis based on your latest Doctordrobe device reading. …",
  "biomarkers": [
    {
      "name": "Salivary Glucose",
      "key": "glucose",
      "value": 4.2,
      "unit": "mg/dL",
      "ref_low": 0.5,
      "ref_high": 7.0,
      "state": "normal",
      "message": "Salivary Glucose is within the reference range. Keep it up!"
    }
  ],
  "quality": {
    "grade": "good",
    "reasons": [],
    "recommended_action": null
  }
}
```

Reports are encrypted with Fernet (`encrypted_data`) before storage; the
`GET /api/checkups/{id}` endpoint returns the decrypted payload.

Every report also carries a **measurement quality** verdict
(`quality.grade` ∈ `good` | `fair` | `poor`, plus human-readable
`reasons` and a `recommended_action`). It is derived from burst
statistics (snapshot-to-snapshot variation, absolute light levels) and
the spectral solver's conditioning/residual; a `poor` grade recommends
retaking the reading so untrustworthy numbers are flagged instead of
printed with false confidence. The grade is stored on each checkup
(`quality_grade`) for list views.

### Calibration (make SaliNet real)

SaliNet ships trained on simulated strip chemistry. To retrain it on
**real measurements**, collect labeled samples and rerun the trainer:

1. **Make control standards** with known concentrations:
   - **Salivary pH** needs no calibration (ratio measurement).
   - **Glucose** — aqueous standards: dissolve pure dextrose powder in
     distilled water at known concentrations (e.g. 0.5 g in 1 L = 50
     mg/dL; weigh on a 0.01 g scale, mix well). Use high-sensitivity
     glucose strips; cover at least 5 concentration levels.
   - **CRP / cortisol / sIgA** — commercial immunoassay control kits or
     lab-prepared standards (home chemistry for these is unreliable;
     plan for a lab session).
2. **Capture samples.** Put a strip under the sensor, arm the firmware:
   `CAL <analyte> <concentration>` in the serial monitor (e.g.
   `CAL glucose 2.5`), then press the button — the device averages 10
   readings and posts one labeled sample. Repeat ≥ 15 samples per level
   across ≥ 5 levels per analyte.
3. **Export and retrain:**
   ```bash
   curl -o backend/data/real_training.csv http://localhost:8000/api/calibration/export
   cd backend && python scripts/train_model.py
   ```
   The trainer uses real samples per analyte (≥ 15) and falls back to
   synthetic data only for analytes you have not calibrated. The
   `salinet.json` manifest records provenance and per-analyte R²/MAE.
4. **Verify** — run a checkup on a known control; the reported value
   should match the standard within the model's MAE.
5. Clear the samples afterwards: `DELETE /api/calibration/samples`.

Endpoints: `POST /api/calibration/samples` (device, `X-API-Key` when
enabled), `GET /api/calibration/samples`, `GET /api/calibration/export`,
`DELETE /api/calibration/samples`.

## Security notes

- **Authentication.** Identity is email + password, hashed with
  `pbkdf2_hmac` (per-user random salt, high iterations) in
  `app/utils/passwords.py`. Sessions are opaque bearer tokens (32 random
  bytes) whose SHA-256 digest is stored in `sessions`, so a database leak
  exposes no usable credentials or tokens. Tokens expire
  (`SESSION_TTL_DAYS`), are revoked on logout/password change/account
  deletion, and login is rate-limited per IP. All ownership checks run
  server-side from the token — endpoints never accept a user id.
- **Fernet key.** `FERNET_KEY` (derived via SHA-256) encrypts reports at
  rest. Generate a strong value:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
  Never commit `.env` files.
- **Device API key.** Set `DEVICE_API_KEY` on the backend to require the
  `X-API-Key` header on `/api/devices/reading`. Comparison is
  constant-time.
- **CORS.** Allowed origins come from `CORS_ORIGINS` (environment), never
  hardcoded.
- **Input validation.** Every endpoint validates via Pydantic v2
  (bounds, enums, lengths). RGB channels are clamped to 0–255, humidity
  to 0–100 %.
- **HTTPS.** In production, terminate TLS at a reverse proxy (see below)
  and set `USE_HTTPS true` in the firmware (NTP sync + trust bundle).

## Testing

| Suite | Command |
| ----- | ------- |
| Backend (pytest, 68 tests) | `cd backend && .venv/Scripts/python -m pytest` |
| Frontend (Vitest + RTL, 26 tests) | `cd frontend && npm test` |
| Frontend lint + typecheck | `cd frontend && npm run lint && npm run build` |
| Firmware compile | `arduino-cli compile --fqbn esp32:esp32:esp32 arduino/doctordrobe` |

CI (`.github/workflows/ci.yml`) runs all of the above plus Docker image
builds on every push/PR to `main`.

## Docs

- [`BUILD.md`](BUILD.md) — step-by-step build tutorial for every component
- [`docs/build-tutorial.html`](docs/build-tutorial.html) — the tutorial as a styled page
- [`arduino/doctordrobe/BUILD_GUIDE.md`](arduino/doctordrobe/BUILD_GUIDE.md) — parts list, wiring, assembly
- [`backend/README.md`](backend/README.md) — backend configuration
- [`frontend/README.md`](frontend/README.md) — frontend scripts and structure

## Production deployment notes

- **Reverse proxy / TLS.** Place the stack behind Caddy/Nginx/Traefik
  terminating HTTPS; forward `X-Forwarded-*` headers. Restrict
  `CORS_ORIGINS` to the real origin(s).
- **Secrets.** Inject `FERNET_KEY` and `DEVICE_API_KEY` via the
  orchestrator's secret store (Kubernetes Secrets, Docker secrets, Vault)
  — never bake them into images.
- **Database.** PostgreSQL 16; enable volume backups and point
  `DATABASE_URL` at a managed instance for HA. Migrations run
  automatically at container start; for blue/green deploys run
  `alembic upgrade head` as a separate migration step.
- **Observability.** The backend emits structured JSON logs (request id,
  method, path, status, duration) to stdout; aggregate with your log
  collector. `/health` supports orchestrator probes.
- **Device fleet.** Per-device API keys with rotation, rate limiting, and
  device registry are the documented next step; the dependency/middleware
  seam in `app/core/security.py` is where they plug in.
