"""Per-document aggregation of chunk-level hits (docs/DOMAIN_MODEL.md sect 3.2)."""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from app.domain.value_objects.search_hit import SearchHit


class MatchResult(BaseModel):
    model_config = {"frozen": True}

    document_id: str
    chunk_hits: tuple[SearchHit, ...]
    average_score: float
    max_score: float
    best_hit: SearchHit

    @model_validator(mode="after")
    def _non_empty(self) -> "MatchResult":
        if not self.chunk_hits:
            raise ValueError("a MatchResult must aggregate at least one chunk hit")
        return self

    @property
    def chunk_count(self) -> int:
        return len(self.chunk_hits)
