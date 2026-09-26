"""API security — optional bearer-token auth and rate limiting.

Both are environment-gated so the local/demo deployment stays friction-free:

* ``FORGE_API_TOKEN`` — when set, every write endpoint requires
  ``Authorization: Bearer <token>`` or ``X-API-Key: <token>``.
* ``FORGE_API_RATE_LIMIT`` — requests per minute per client (default 60),
  keyed by API token when auth is on, otherwise by client IP.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from .. import config

_invocations: dict[str, deque[float]] = defaultdict(deque)
_WINDOW_S = 60.0


def _client_key(request: Request) -> str:
    header = request.headers.get("authorization", "")
    api_key = request.headers.get("x-api-key", "")
    if api_key:
        return f"token:{api_key}"
    if header.lower().startswith("bearer "):
        return f"token:{header[len('bearer '):]}"
    xff = request.headers.get("x-forwarded-for", "")
    host = (xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown"))
    return f"ip:{host}"


def require_token(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Fail closed on write routes when ``FORGE_API_TOKEN`` is configured."""
    if not config.API_TOKEN:
        return
    supplied = x_api_key or ""
    if not supplied and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization.split(" ", 1)[1].strip()
    if not supplied or supplied != config.API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


def rate_limit(request: Request) -> None:
    """Sliding-window rate limiter applied to all API routes."""
    key = _client_key(request)
    now = time.monotonic()
    window = _invocations[key]
    while window and window[0] < now - _WINDOW_S:
        window.popleft()
    if len(window) >= config.API_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {config.API_RATE_LIMIT} requests per {int(_WINDOW_S)}s",
        )
    window.append(now)