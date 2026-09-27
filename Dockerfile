# FORGE — single-service image (Hugging Face Space / one-port deploy)
# Serves the FastAPI backend (8000) + Next.js app (7860) behind one container.
# Frontend calls /api/* on its own origin; `next start` rewrites those to :8000.

# ---- backend stage ---------------------------------------------------------
FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Node 22 runtime so the engine can execute JS/TS validation suites (vitest/tsc)
RUN apt-get update && apt-get install -y --no-install-recommends curl xz-utils ca-certificates \
    && NODE_ARCH=$(case "$(uname -m)" in aarch64|arm64) echo arm64;; *) echo x64;; esac) \
    && curl -fsSL "https://nodejs.org/dist/v22.12.0/node-v22.12.0-linux-${NODE_ARCH}.tar.xz" \
       | tar -xJ -C /usr/local --strip-components=1 \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version

COPY backend/app /app/app
COPY forgemart /forgemart
RUN cd /forgemart && rm -rf node_modules package-lock.json && npm install --no-audit --no-fund

ENV FORGE_DATA_DIR=/data \
    FORGE_WORKSPACES_DIR=/data/workspaces \
    FORGE_UPLOADS_DIR=/data/uploads \
    FORGE_SKILLS_DIR=/app/app/skills \
    FORGEMART_DIR=/forgemart \
    FORGE_DB_URL=sqlite:////data/forge.db

RUN mkdir -p /data/workspaces /data/uploads

# ---- frontend build (glibc node so artifacts match python-slim runtime) ----
FROM node:22-slim AS fe-build
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV NEXT_PUBLIC_API_URL="" \
    NEXT_PUBLIC_API_TOKEN="" \
    BACKEND_INTERNAL_URL="http://127.0.0.1:8000"
RUN npm run build

# ---- final image -----------------------------------------------------------
FROM backend
EXPOSE 7860
COPY --from=fe-build /fe/package.json /fe/package-lock.json /fe/
RUN cd /fe && npm ci --omit=dev
COPY --from=fe-build /fe/.next /fe/.next
COPY --from=fe-build /fe/next.config.ts /fe/
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 & cd /fe && npx next start -p 7860"]