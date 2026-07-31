# Doctordrobe frontend image — multi-stage:
#   1. Build the React SPA with Node 20.
#   2. Serve the static bundle with Nginx (see infra/nginx/frontend.conf).
# Build context: repository root (docker-compose passes `context: ..`).
FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

COPY frontend/ .
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY infra/nginx/frontend.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD wget -q -O - http://localhost/health || exit 1
