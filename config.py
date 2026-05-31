"""Centralized configuration for the agenticJob pipeline.

All model identifiers, tuning constants, and credentials are read here so the
rest of the codebase has a single source of truth.
"""
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    gemini_flash_model: str = "gemini-2.5-flash"
    gemini_pro_model: str = "gemini-2.5-pro"
    claude_model: str = "claude-3-5-sonnet-20241022"

    fit_threshold: int = Field(default=70, ge=0, le=100)
    portfolio_cache_ttl_seconds: int = Field(default=3600, gt=0)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)

    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    jsearch_api_key: Optional[str] = None
    adzuna_app_id: Optional[str] = None
    adzuna_app_key: Optional[str] = None


settings = Settings()
