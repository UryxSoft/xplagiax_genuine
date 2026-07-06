"""Application settings loaded from environment variables (.env)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ParserSettings(BaseSettings):
    """Configuration for the extraction stage (MarkItDown + GROBID)."""

    model_config = SettingsConfigDict(env_prefix="PARSER_", env_file=".env", extra="ignore")

    grobid_base_url: str = Field(default="http://localhost:8070")
    grobid_timeout_seconds: float = Field(default=30.0, gt=0)
    grobid_enabled: bool = Field(default=True)
    scanned_min_chars_per_page: int = Field(
        default=200,
        description="Below this average char/page count, a PDF is flagged as scanned (needs OCR).",
    )
