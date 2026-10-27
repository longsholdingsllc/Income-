# Income (Autopilot — Passive Income OS): one service serving API + SPA.
# Stage 1: build the React frontend. Stage 2: FastAPI backend serves the
# built frontend same-origin (see backend/server.py SPA fallback).
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install --legacy-peer-deps
COPY frontend/ ./
RUN CI=true npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY --from=web /web/build ./frontend/build
EXPOSE 8000
CMD ["sh", "-c", "uvicorn server:app --app-dir /app/backend --host 0.0.0.0 --port ${PORT:-8000}"]
