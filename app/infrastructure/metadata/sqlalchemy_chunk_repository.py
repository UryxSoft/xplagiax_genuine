"""Implements ChunkRepository over SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.chunk import Chunk
from app.infrastructure.metadata.mappers import chunk_to_orm, orm_to_chunk
from app.infrastructure.metadata.orm import ChunkModel


class SqlAlchemyChunkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_all(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        for chunk in chunks:
            self._session.merge(chunk_to_orm(chunk))
        self._session.commit()

    def by_ids(self, chunk_ids: list[int]) -> list[Chunk]:
        if not chunk_ids:
            return []
        stmt = select(ChunkModel).where(ChunkModel.id.in_(chunk_ids))
        models = self._session.execute(stmt).scalars().all()
        return [orm_to_chunk(m) for m in models]

    def by_document(self, document_id: str) -> list[Chunk]:
        stmt = (
            select(ChunkModel)
            .where(ChunkModel.document_id == document_id)
            .order_by(ChunkModel.chunk_order)
        )
        models = self._session.execute(stmt).scalars().all()
        return [orm_to_chunk(m) for m in models]

    def ids_for_documents(self, document_ids: list[str]) -> list[int]:
        if not document_ids:
            return []
        stmt = select(ChunkModel.id).where(ChunkModel.document_id.in_(document_ids))
        return list(self._session.execute(stmt).scalars().all())
