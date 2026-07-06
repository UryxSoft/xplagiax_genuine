"""Detected language of a document or query segment (RF-06)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Language(BaseModel):
    model_config = {"frozen": True}

    code: str = Field(min_length=2, max_length=2, description="ISO-639-1 code")
    confidence: float = Field(ge=0.0, le=1.0)
