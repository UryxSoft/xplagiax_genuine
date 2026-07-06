"""SQLAlchemy ORM schema for Document/Chunk metadata (ADR-009: PostgreSQL
holds metadata, TurboVec holds embeddings, related by ChunkId).

Note: ChunkId is uint64 in the domain (shared key with TurboVec's
IdMapIndex) but stored here as a signed BigInteger. Ids are assigned
sequentially by our own indexing pipeline, so they never approach the
unsigned/signed boundary in practice; this is a deliberate simplification,
not an oversight.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)

    source_filename: Mapped[str]
    source_path: Mapped[str]
    source_pages: Mapped[int]
    source_mime: Mapped[str]
    source_size_bytes: Mapped[int]

    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    bib_title: Mapped[str | None]
    bib_authors: Mapped[list] = mapped_column(JSON, default=list)
    bib_institution: Mapped[str | None]
    bib_faculty: Mapped[str | None]
    bib_career: Mapped[str | None]
    bib_year: Mapped[int | None]

    language_code: Mapped[str | None] = mapped_column(String(2))
    language_confidence: Mapped[float | None]
    topic_domain: Mapped[str | None]
    topic_confidence: Mapped[float | None]

    keywords: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str]
    indexed_at: Mapped[datetime | None]


class ChunkModel(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)

    text: Mapped[str]
    span_start: Mapped[int]
    span_end: Mapped[int]
    span_page: Mapped[int | None]
    chunk_order: Mapped[int]
