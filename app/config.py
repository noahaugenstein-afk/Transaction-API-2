"""Application configuration, loaded from environment variables (.env supported)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Public base URL of this service (used to build download links) ---
    # On Railway this is set automatically from RAILWAY_PUBLIC_DOMAIN; otherwise set it yourself.
    public_base_url: str = "http://localhost:8000"

    # --- API key the custom GPT must send in the X-API-Key header ---
    # Generate a long random string and keep it secret.
    api_key: str = "changeme-set-a-real-key"

    # --- Filesystem locations ---
    templates_dir: Path = BASE_DIR / "templates"
    mappings_dir: Path = BASE_DIR / "mappings"
    output_dir: Path = BASE_DIR / "output"

    # Which worksheet template + mapping to use by default.
    default_template: str = "commission_worksheet.pdf"
    default_mapping: str = "commission_fields.json"

    # How long a generated PDF stays downloadable (minutes) before cleanup.
    output_ttl_minutes: int = 120

    # --- Optional server-side extraction (off by default) ---
    extraction_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    def resolved_base_url(self) -> str:
        # Railway injects RAILWAY_PUBLIC_DOMAIN; prefer it when present.
        import os

        domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        if domain:
            return f"https://{domain}"
        return self.public_base_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.output_dir.mkdir(parents=True, exist_ok=True)
    return s
