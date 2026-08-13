# Doctordrobe Build Tutorial

Step-by-step guide to building and running every component of the
Doctordrobe health analyzer: backend, frontend, Docker stack, and the
ESP32 firmware. An HTML version of this tutorial is available in
[`docs/build-tutorial.html`](docs/build-tutorial.html).

---

## 1. Prerequisites

| Tool | Version | Needed for |
| ---- | ------- | ---------- |
| Python | 3.11+ | Backend (FastAPI, pytest) |
| Node.js + npm | 20.x | Frontend (Vite, Vitest) |
| Docker + Docker Compose | latest | Full stack / container builds |
| arduino-cli or Arduino IDE 2.x | 1.x / 2.x | Firmware compile & flash |
| Git | any | Source control |

Verify:

```bash
python --version      # 3.11.x
node --version        # v20.x
docker --version
docker compose version
arduino-cli version   # optional
```

---

## 2. Backend

### 2.1 Install and configure

```bash
cd backend
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env   # edit if needed (defaults work for local dev)
```

### 2.2 Create the database schema

```bash
alembic upgrade head
```

This runs the initial migration against SQLite (`doctordrobe.db` by
default) or any `DATABASE_URL` you configure.

### 2.3 Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/health

### 2.4 Run the tests

```bash
pytest -q        # expect: 68 passed
```

---

## 3. Frontend

### 3.1 Install and run dev server

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173. The dev config points the API client at
`http://localhost:8000` (see `.env.development`). Add
`http://localhost:5173` to `CORS_ORIGINS` in the backend `.env` if the
browser blocks requests.

### 3.2 Quality gates

```bash
npm test          # Vitest + React Testing Library — expect: 26 passed
npm run lint      # ESLint, zero warnings allowed
npm run build     # strict tsc typecheck + production bundle in dist/
```

---

## 4. Full stack with Docker Compose

```bash
cp .env.example .env        # set FERNET_KEY, DEVICE_API_KEY
docker compose -f infra/docker-compose.yml up --build
```

What happens:

1. `postgres` starts and becomes healthy (`pg_isready`).
2. `backend` waits for postgres, runs `alembic upgrade head`, then
   serves uvicorn on port 8000. Healthchecked via `curl /health`.
3. `frontend` waits for backend, serves the SPA via Nginx on port 80,
   proxying `/api/*` to the backend. Healthchecked via `wget /health`.

Verify:

```bash
curl http://localhost/health                  # ok
curl http://localhost/api/devices/status?device_id=doctordrobe_demo_001
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"correct-horse-9!","age":34,"sex":"female","height_cm":165,"weight_kg":62}'
```

The register response includes a bearer `token`; send it as
`Authorization: Bearer <token>` on every other request (the SPA does this
automatically).

Stop with `docker compose -f infra/docker-compose.yml down -v`
(`-v` also deletes the postgres volume).

### Building images manually

```bash
docker build -t doctordrobe-backend:local backend
docker build -t doctordrobe-frontend:local -f frontend/Dockerfile .
```

---

## 5. ESP32 firmware

> **Building the physical device (parts list, wiring, assembly)?
> See [`arduino/doctordrobe/BUILD_GUIDE.md`](arduino/doctordrobe/BUILD_GUIDE.md).**

### 5.1 Toolchain

```bash
arduino-cli core update-index
arduino-cli core install esp32:esp32@2.0.14
arduino-cli lib install "Adafruit TCS34725" "DHT sensor library" "ArduinoJson"
```

(Arduino IDE 2.x users: install the same via Library Manager / Boards
Manager.)

### 5.2 Configure

```bash
cd arduino/doctordrobe
cp secrets.h.example secrets.h
```

Edit `config.h`:

| Setting | Example | Meaning |
| ------- | ------- | ------- |
| `WIFI_SSID` / `WIFI_PASS` | `"my_wifi"` | Your network |
| `BACKEND_HOST` / `BACKEND_PORT` | `"192.168.1.100"` / `8000` | API address |
| `USE_HTTPS` | `false` | TLS on/off |
| `DEVICE_ID` | `"doctordrobe_demo_001"` | Must match the app's Device ID |

Edit `secrets.h` (git-ignored):

```cpp
#define DEVICE_API_KEY "your-generated-api-key"   // only if backend requires it
```

### 5.3 Compile

```bash
arduino-cli compile --fqbn esp32:esp32:esp32 doctordrobe
```

Expected result:

```
Sketch uses 795825 bytes (60%) of program storage space.
Global variables use 45296 bytes (13%) of dynamic memory.
```

### 5.4 Flash and run

```bash
arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32 doctordrobe   # Windows
arduino-cli upload -p /dev/ttyUSB0 --fqbn esp32:esp32:esp32 doctordrobe  # Linux/macOS
```

Wiring (ESP32 DevKit): TCS34725 → I2C SDA=GPIO21, SCL=GPIO22; DHT22 →
GPIO4; button → GPIO0-GND; LED → GPIO2.

Behaviour:

- Boot: connects to Wi-Fi (retry every 5 s, up to 20 attempts), syncs
  NTP when HTTPS is enabled.
- Button press: reads sensors, POSTs to `/api/devices/reading`.
- LED blinks 3x on HTTP 200/201; stays on 5 s on failure.

---

## 6. Continuous integration

`.github/workflows/ci.yml` runs on every push/PR to `main`:

1. **backend-tests** — Python 3.11, `pytest -v` (plus an Alembic smoke
   migration).
2. **frontend-tests** — Node 20, `npm ci`, `npm run lint`, `npm run
   build`, `npm test`.
3. **docker-build** — builds both images to catch Dockerfile regressions.

---

## 7. Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `sqlite3.OperationalError` on boot | Run `alembic upgrade head` first |
| CORS errors in the browser | Add the SPA origin to `CORS_ORIGINS` in the backend `.env` |
| Checkup returns 409 "No device reading" | Press the device button, then check `/api/devices/status?device_id=...` |
| Device LED stays on 5 s | Backend unreachable: check `BACKEND_HOST`/port, Wi-Fi, firewall, `DEVICE_API_KEY` |
| `X-API-Key` rejected | Generate the key on the backend and mirror it in `secrets.h` |
| `import pysqlite not async` | Use `sqlite+aiosqlite://` in `DATABASE_URL` (the app normalizes plain `sqlite://`) |
| Firmware TLS handshake fails | Ensure NTP sync succeeded; use a trusted CA or set `USE_HTTPS false` for LAN |
| Postgres not ready at backend start | `depends_on` + healthcheck handles it; check `docker compose ps` |
| Tests fail after switching DB | Tests always use in-memory SQLite; remove stale `doctordrobe.db` before re-running migrations |

---

## 8. Docs and specs

- `README.md` — product docs, API reference, security notes
- `backend/README.md` — backend layout and configuration
- `frontend/README.md` — frontend scripts and structure
- `arduino/doctordrobe/README.md` — hardware wiring and flashing
- `docs/build-tutorial.html` — this tutorial as a styled page
