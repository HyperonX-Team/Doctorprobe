# Doctordrobe Frontend

React 18 + TypeScript (strict) + Vite 5 + Tailwind 3.4 SPA for the
Doctordrobe home-health analyzer. Full product docs live in the
[root README](../README.md); this file covers frontend specifics.

## Stack

- React 18, `react-router-dom` (data router), plain controlled forms
- TypeScript strict (`noUnusedLocals`, `noUnusedParameters`, …)
- Tailwind 3.4 with a custom `brand` palette and animations
- Vitest 2 + React Testing Library + Jest-DOM (26 tests)
- ESLint 9 flat config (typescript-eslint, react-hooks, prettier)

## Scripts

| Command | Purpose |
| ------- | ------- |
| `npm run dev` | Vite dev server (port 5173) |
| `npm run build` | `tsc -b` typecheck + production build |
| `npm test` | Vitest (jsdom) |
| `npm run lint` | ESLint, zero warnings allowed |
| `npm run format` | Prettier over `src` |

## API base URL

| Env file | `VITE_API_BASE_URL` | Used when |
| -------- | ------------------- | --------- |
| `.env.development` | `http://localhost:8000` | local dev |
| `.env.production` | `/api` | Nginx container (proxied) |

## Structure

```
src/
  api/         typed fetch client + endpoint constants (no secrets)
  types/       mirrors backend Pydantic schemas
  context/     UserProvider (bearer-token session)
  hooks/       useUser, useCheckup, useDeviceStatus (polling)
  components/  layout shell, ChatBubble, ReportTable, Toast, dialogs…
  pages/       Welcome, Login, Home, Checkup, Report, History, Trends, Vault, Settings
  utils/       formatters, error messages
tests/         welcome, login, checkup, trends, toast, confirm-dialog, useUser
```

Every page has explicit loading, empty, and error states; non-2xx
responses surface the backend `detail` message via `ApiError`.

## Docker

Multi-stage build (Node 20 → Nginx). Build context is the repository
root so the image can copy `infra/nginx/frontend.conf`:

```bash
docker build -t doctordrobe-frontend -f frontend/Dockerfile .
```
