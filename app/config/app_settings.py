"""Consolidated runtime settings for wiring the production Flask app (wsgi.py)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(default="postgresql+psycopg://xplagiax:xplagiax@localhost:5432/xplagiax")

    embedding_model_name: str = Field(default="intfloat/multilingual-e5-large")
    embedding_device: str = Field(default="cpu")
    embedding_batch_size: int = Field(default=32, gt=0)

    turbovec_index_path: Path = Field(default=Path("/data/turbovec/index.tvim"))
    turbovec_bit_width: int = Field(default=4)

    chunk_min_tokens: int = Field(default=300, gt=0)
    chunk_max_tokens: int = Field(default=500, gt=0)
    chunk_overlap_ratio: float = Field(default=0.2, ge=0.0, lt=1.0)

    topic_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    search_top_k_per_segment: int = Field(default=10, gt=0)
