"""Detected academic domain/topic of a document or query segment (RF-07)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Topic(BaseModel):
    model_config = {"frozen": True}

    domain: str
    confidence: float = Field(ge=0.0, le=1.0)
