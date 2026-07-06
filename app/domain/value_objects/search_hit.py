"""A single vector-index search result: a ChunkId and its similarity score."""

from __future__ import annotations

from pydantic import BaseModel


class SearchHit(BaseModel):
    model_config = {"frozen": True}

    chunk_id: int
    score: float
