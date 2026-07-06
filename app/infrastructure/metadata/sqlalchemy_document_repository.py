"""Implements DocumentRepository over SQLAlchemy (ADR-009: PostgreSQL for metadata)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.document import Document
from app.domain.value_objects.sha256_hash import Sha256Hash
from app.infrastructure.metadata.mappers import document_to_orm, orm_to_document
from app.infrastructure.metadata.orm import DocumentModel

_PAGE_SIZE = 20


class SqlAlchemyDocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, document: Document) -> None:
        self._session.merge(document_to_orm(document))
        self._session.commit()

    def by_id(self, document_id: str) -> Document | None:
        model = self._session.get(DocumentModel, document_id)
        return orm_to_document(model) if model is not None else None

    def by_hash(self, tenant_id: str, content_hash: Sha256Hash) -> Document | None:
        stmt = select(DocumentModel).where(
            DocumentModel.tenant_id == tenant_id,
            DocumentModel.content_hash == content_hash.hex,
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return orm_to_document(model) if model is not None else None

    def list(
        self, tenant_id: str, language: str | None = None, topic: str | None = None, page: int = 1
    ) -> list[Document]:
        if page < 1:
            raise ValueError("page must be >= 1")

        stmt = select(DocumentModel).where(DocumentModel.tenant_id == tenant_id)
        if language is not None:
            stmt = stmt.where(DocumentModel.language_code == language)
        if topic is not None:
            stmt = stmt.where(DocumentModel.topic_domain == topic)

        stmt = stmt.order_by(DocumentModel.id).offset((page - 1) * _PAGE_SIZE).limit(_PAGE_SIZE)
        models = self._session.execute(stmt).scalars().all()
        return [orm_to_document(m) for m in models]

    def delete(self, document_id: str) -> None:
        model = self._session.get(DocumentModel, document_id)
        if model is not None:
            self._session.delete(model)
            self._session.commit()
