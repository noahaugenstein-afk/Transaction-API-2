"""FastAPI application entrypoint.

Run locally:   uvicorn app.main:app --reload
Interactive docs at /docs once running.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_settings
from .routes import router

app = FastAPI(
    title="Lee Transaction Automation API",
    version=__version__,
    description=(
        "Fills a commercial real-estate Commission Worksheet from structured "
        "transaction data and returns the completed PDF. Built to back a custom "
        "GPT Action."
    ),
)

# A custom GPT calls the API server-to-server, so CORS is permissive but the
# endpoints are still protected by the X-API-Key header.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["health"])
async def root():
    settings = get_settings()
    return {
        "service": "Lee Transaction Automation API",
        "version": __version__,
        "status": "ok",
        "base_url": settings.resolved_base_url(),
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health():
    return {"status": "healthy"}
