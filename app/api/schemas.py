"""Request/response schemas for the HTTP API (docs/ARCHITECTURE.md sect 9).

Search is synchronous in this deliverable: RF-13's async job_id/polling
contract requires the Jobs service (Redis-backed state machine, Celery
workers) described in the ADR, which no sprint has built yet. Documented
as a gap, not silently implemented as a fire-and-forget stub.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequestSchema(BaseModel):
    text: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    top_k_per_segment: int = Field(default=10, gt=0, le=100)


class ChunkMatchSchema(BaseModel):
    texto: str
    score: float
    pagina: int | None = None


class DocumentMatchSchema(BaseModel):
    documento: str
    universidad: str | None
    autores: list[str]
    idioma: str | None
    tema: str | None
    similaridad: float
    chunks: int
    chunk_mas_parecido: ChunkMatchSchema


class SearchResponseSchema(BaseModel):
    query_language: str
    query_topic: str
    global_plagiarism_percent: float
    documents: list[DocumentMatchSchema]
