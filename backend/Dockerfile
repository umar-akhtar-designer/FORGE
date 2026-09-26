# FORGE backend — production image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Node 22 runtime so the engine can execute JS/TS validation suites (vitest/tsc)
RUN apt-get update && apt-get install -y --no-install-recommends curl xz-utils ca-certificates \
    && NODE_ARCH=$(case "$(uname -m)" in aarch64|arm64) echo arm64;; *) echo x64;; esac) \
    && curl -fsSL "https://nodejs.org/dist/v22.12.0/node-v22.12.0-linux-${NODE_ARCH}.tar.xz" \
       | tar -xJ -C /usr/local --strip-components=1 \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version

# App code, bundled skills, and the demo repo it indexes at boot
COPY backend/app /app/app
COPY forgemart /forgemart
COPY backend/requirements.txt /app/requirements.txt

ENV FORGE_DATA_DIR=/data \
    FORGE_WORKSPACES_DIR=/data/workspaces \
    FORGE_UPLOADS_DIR=/data/uploads \
    FORGE_SKILLS_DIR=/app/app/skills \
    FORGEMART_DIR=/forgemart \
    FORGE_DB_URL=sqlite:////data/forge.db

RUN mkdir -p /data/workspaces /data/uploads

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://127.0.0.1:8000/api/health').status_code==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]