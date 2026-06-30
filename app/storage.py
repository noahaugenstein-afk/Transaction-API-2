"""Stores generated PDFs and builds download URLs, with simple TTL cleanup."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from .config import get_settings


def new_output_path(prefix: str = "commission_worksheet") -> tuple[Path, str]:
    """Return (filesystem path, token) for a fresh output file."""
    settings = get_settings()
    token = uuid.uuid4().hex
    filename = f"{prefix}_{token}.pdf"
    return settings.output_dir / filename, token


def public_url_for(filename: str) -> str:
    settings = get_settings()
    return f"{settings.resolved_base_url()}/download/{filename}"


def cleanup_expired() -> int:
    """Delete output PDFs older than the configured TTL. Returns count removed."""
    settings = get_settings()
    ttl_seconds = settings.output_ttl_minutes * 60
    now = time.time()
    removed = 0
    for f in settings.output_dir.glob("*.pdf"):
        try:
            if now - f.stat().st_mtime > ttl_seconds:
                f.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def resolve_download(filename: str) -> Path | None:
    """Return the path for a download filename if it exists and is inside output_dir."""
    settings = get_settings()
    # Prevent path traversal: only allow plain filenames.
    if "/" in filename or "\\" in filename or ".." in filename:
        return None
    path = (settings.output_dir / filename).resolve()
    if settings.output_dir.resolve() not in path.parents:
        return None
    return path if path.exists() else None


def _template_cache_dir() -> Path:
    settings = get_settings()
    d = settings.output_dir / "_templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_uploaded_template(pdf_bytes: bytes) -> str:
    """Store an uploaded template PDF and return a token to reference it later."""
    token = uuid.uuid4().hex
    (_template_cache_dir() / f"{token}.pdf").write_bytes(pdf_bytes)
    return token


def resolve_template_token(token: str) -> Path | None:
    if not token or any(c in token for c in "/\\.."):
        return None
    path = (_template_cache_dir() / f"{token}.pdf").resolve()
    if _template_cache_dir().resolve() not in path.parents:
        return None
    return path if path.exists() else None


def cleanup_expired_templates() -> int:
    settings = get_settings()
    ttl_seconds = settings.output_ttl_minutes * 60
    now = time.time()
    removed = 0
    for f in _template_cache_dir().glob("*.pdf"):
        try:
            if now - f.stat().st_mtime > ttl_seconds:
                f.unlink()
                removed += 1
        except OSError:
            pass
    return removed
