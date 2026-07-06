"""Output of the segmentation stage (RF-05), prior to ChunkId assignment.

A TextSegment becomes a Chunk entity once the indexing pipeline assigns it
a persistent uint64 id shared with TurboVec (docs/DOMAIN_MODEL.md sect 2.2).
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.domain.value_objects.token_span import TokenSpan


class TextSegment(BaseModel):
    """One chunk-sized piece of text produced by the chunker."""

    model_config = {"frozen": True}

    text: str
    span: TokenSpan
    order: int

    @field_validator("text")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("segment text must not be empty")
        return value
