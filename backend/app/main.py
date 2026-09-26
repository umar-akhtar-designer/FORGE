"""FORGE backend entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .api.routes import router as api_router
from .db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=config.APP_NAME, description=config.APP_TAGLINE, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

APP_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>FORGE API</title></head>
<body style="font-family:system-ui;background:#080A0D;color:#EDE8E2;padding:3rem">
<h1>FORGE &mdash; Autonomous Engineering Control Plane</h1>
<p>API is running. Interactive docs at <a href="/docs" style="color:#FF6B2C">/docs</a>.</p>
<p>Frontend command center: <code>cd frontend &amp;&amp; npm run dev</code></p>
</body></html>"""


@app.get("/", include_in_schema=False)
def index():
    return APP_HTML