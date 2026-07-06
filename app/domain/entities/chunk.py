"""Chunk entity -- persistence-oriented fields (docs/DOMAIN_MODEL.md sect 2.2).

`id` is the same uint64 shared with TurboVec's IdMapIndex (shared kernel,
docs/DOMAIN_MODEL.md sect 7): assigned by the indexing pipeline before
persistence, not generated here.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.value_objects.token_span import TokenSpan


class Chunk(BaseModel):
    model_config = {"frozen": True}

    id: int
    document_id: str
    text: str
    span: TokenSpan
    order: int
