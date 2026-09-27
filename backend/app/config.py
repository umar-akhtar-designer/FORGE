"""FORGE backend configuration and path resolution.

All paths resolve relative to this file so the engine runs headless,
inside FastAPI, or from tests without special setup.
"""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FORGE_ROOT = Path(os.environ.get("FORGE_ROOT", BACKEND_DIR.parent))

FORGEMART_DIR = Path(os.environ.get("FORGEMART_DIR", FORGE_ROOT / "forgemart"))
DATA_DIR = Path(os.environ.get("FORGE_DATA_DIR", BACKEND_DIR / "data"))
WORKSPACES_DIR = Path(os.environ.get("FORGE_WORKSPACES_DIR", BACKEND_DIR / "workspaces"))

DB_URL = os.environ.get("FORGE_DB_URL", f"sqlite:///{DATA_DIR / 'forge.db'}")
UPLOADS_DIR = Path(os.environ.get("FORGE_UPLOADS_DIR", DATA_DIR / "uploads"))

ALLOWED_REPOS = {"forgemart"}

MAX_UPLOAD_BYTES = 60 * 1024 * 1024      # 60 MB zip
MAX_ZIP_ENTRIES = 3000
MAX_UNCOMPRESSED_BYTES = 400 * 1024 * 1024  # zip-bomb guard

# ---- Generative repair (optional, off by default for determinism) ----
# Any OpenAI-compatible endpoint works. The default (Pollinations) needs no key.
LLM_ENABLED = os.environ.get("FORGE_LLM_ENABLED", "").lower() in {"1", "true", "yes", "on"}
LLM_BASE_URL = os.environ.get("FORGE_LLM_BASE_URL", "https://text.pollinations.ai/openai")
LLM_API_KEY = os.environ.get("FORGE_LLM_API_KEY", "")
LLM_MODEL = os.environ.get("FORGE_LLM_MODEL", "openai")
LLM_FALLBACK_BASE_URL = os.environ.get("FORGE_LLM_FALLBACK_URL", "https://text.pollinations.ai/openai")
LLM_FALLBACK_MODEL = os.environ.get("FORGE_LLM_FALLBACK_MODEL", "openai")
LLM_TIMEOUT_S = float(os.environ.get("FORGE_LLM_TIMEOUT_S", "90"))
SKILL_LEARNING = os.environ.get("FORGE_SKILL_LEARNING", "true").lower() in {"1", "true", "yes", "on"}

API_TOKEN = os.environ.get("FORGE_API_TOKEN", "")
API_RATE_LIMIT = int(os.environ.get("FORGE_API_RATE_LIMIT", "300"))
LLM_MAX_FILES = int(os.environ.get("FORGE_LLM_MAX_FILES", "3"))
LLM_MAX_FILE_BYTES = int(os.environ.get("FORGE_LLM_MAX_FILE_BYTES", "80000"))

# ---- GitHub PR (optional, off until a token is configured) ----
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")   # "owner/name"
GITHUB_DEFAULT_BRANCH = os.environ.get("GITHUB_DEFAULT_BRANCH", "main")

APP_NAME = "FORGE"
APP_TAGLINE = "Autonomous Engineering Control Plane"
APP_TAGLINE_SHORT = "From Issue -> Root Cause -> Release"

MAX_PARALLEL_INVESTIGATORS = 4

EXCLUDED_DIRS = {
    ".git", ".next", "node_modules", "dist", "build", "coverage", ".nyc_output",
    ".turbo", "out", ".cache", "venv", ".venv", "__pycache__", ".pytest_cache",
    "data", "workspaces", ".DS_Store",
}
EXCLUDED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf", ".map", ".lock", ".svg"}


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not FORGEMART_DIR.exists():
        raise FileNotFoundError(f"ForgeMart repository not found at {FORGEMART_DIR}")