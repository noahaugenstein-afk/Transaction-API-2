"""Simple API-key authentication for the custom GPT Action."""

from fastapi import Header, HTTPException, status

from .config import get_settings


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    settings = get_settings()
    if not settings.api_key or settings.api_key == "changeme-set-a-real-key":
        # Fail closed if the operator never set a real key.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server API key is not configured. Set API_KEY in the environment.",
        )
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
        )
