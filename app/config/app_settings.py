"""Consolidated runtime settings for wiring the production Flask app (wsgi.py)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(default="postgresql+psycopg://xplagiax:xplagiax@localhost:5432/xplagiax")

    # "sentence-transformers" loads embedding_model_name via torch;
    # "onnx" loads an exported model from onnx_model_dir (see
    # OnnxEmbeddingAdapter) -- the low-RAM/CPU production profile.
    embedding_backend: str = Field(default="sentence-transformers", pattern="^(sentence-transformers|onnx)$")
    embedding_model_name: str = Field(default="intfloat/multilingual-e5-large")
    embedding_device: str = Field(default="cpu")
    embedding_batch_size: int = Field(default=32, gt=0)
    onnx_model_dir: Path = Field(default=Path("/models/e5-small-onnx"))
    onnx_model_filename: str = Field(default="model.onnx")

    redis_url: str | None = Field(default=None)
    search_cache_ttl_seconds: int = Field(default=300, gt=0)
    search_cache_max_entries: int = Field(default=1000, gt=0)

    turbovec_index_path: Path = Field(default=Path("/data/turbovec/index.tvim"))
    turbovec_bit_width: int = Field(default=4)

    # --- Fase 3: single-writer topology (ADR-010) ---
    # "local": this process owns the index and writes synchronously.
    # "worker": web replicas hold a read-only hot-reloading view; every
    # write becomes a job for the indexer worker (requires redis_url).
    index_write_mode: str = Field(default="local", pattern="^(local|worker)$")
    index_data_dir: Path = Field(default=Path("/data/turbovec"))
    index_checkpoint_every_ops: int = Field(default=50, gt=0)

    jobs_stream_key: str = Field(default="xplagiax:jobs")
    jobs_consumer_group: str = Field(default="xplagiax-workers")
    jobs_consumer_name: str = Field(default="worker-1")
    job_ttl_seconds: int = Field(default=7 * 24 * 3600, gt=0)

    chunk_min_tokens: int = Field(default=300, gt=0)
    chunk_max_tokens: int = Field(default=500, gt=0)
    chunk_overlap_ratio: float = Field(default=0.2, ge=0.0, lt=1.0)

    topic_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    search_top_k_per_segment: int = Field(default=10, gt=0)
