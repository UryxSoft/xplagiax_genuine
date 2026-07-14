"""SqlAlchemy repository coverage for the Fase 1 additions: institution/
country filters, counts, and chunk deletion by document."""

from __future__ import annotations

from app.domain.entities.chunk import Chunk
from app.domain.entities.document import Document
from app.domain.entities.document_status import DocumentStatus
from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata
from app.domain.value_objects.language import Language
from app.domain.value_objects.pdf_source import PdfSource
from app.domain.value_objects.sha256_hash import Sha256Hash
from app.domain.value_objects.token_span import TokenSpan
from app.domain.value_objects.topic import Topic
from app.infrastructure.metadata.sqlalchemy_chunk_repository import SqlAlchemyChunkRepository
from app.infrastructure.metadata.sqlalchemy_document_repository import SqlAlchemyDocumentRepository


def _document(
    doc_id: str,
    tenant_id: str = "tenant-a",
    institution: str | None = "Universidad Nacional",
    country: str | None = "Peru",
    language: str = "es",
    topic: str = "Ingenieria",
) -> Document:
    return Document(
        id=doc_id,
        tenant_id=tenant_id,
        source=PdfSource(
            filename=f"{doc_id}.txt", path="inline://text", pages=0, mime="text/plain", size_bytes=10
        ),
        content_hash=Sha256Hash.of(doc_id),
        bibliography=BibliographicMetadata(institution=institution, country=country),
        language=Language(code=language, confidence=0.9),
        topic=Topic(domain=topic, confidence=0.9),
        status=DocumentStatus.INDEXED,
    )


def _chunk(chunk_id: int, document_id: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        document_id=document_id,
        text="texto",
        span=TokenSpan(start=0, end=5),
        order=0,
    )


def test_country_round_trips_through_orm(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    repo.save(_document("doc-1", country="Chile"))

    fetched = repo.by_id("doc-1")
    assert fetched is not None
    assert fetched.bibliography.country == "Chile"


def test_list_filters_by_institution_case_insensitive(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    repo.save(_document("doc-1", institution="Universidad Nacional"))
    repo.save(_document("doc-2", institution="Universidad de Chile"))

    result = repo.list("tenant-a", institution="universidad nacional")

    assert [d.id for d in result] == ["doc-1"]


def test_list_filters_by_country_case_insensitive(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    repo.save(_document("doc-1", country="Peru"))
    repo.save(_document("doc-2", country="Chile"))

    result = repo.list("tenant-a", country="CHILE")

    assert [d.id for d in result] == ["doc-2"]


def test_list_combines_all_filters(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    repo.save(_document("doc-1", language="es", topic="Ingenieria", country="Peru"))
    repo.save(_document("doc-2", language="es", topic="Derecho", country="Peru"))
    repo.save(_document("doc-3", language="en", topic="Ingenieria", country="Peru"))
    repo.save(_document("doc-4", language="es", topic="Ingenieria", country="Chile"))

    result = repo.list(
        "tenant-a", language="es", topic="Ingenieria", country="Peru",
        institution="Universidad Nacional",
    )

    assert [d.id for d in result] == ["doc-1"]


def test_list_null_metadata_never_matches_filter(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    repo.save(_document("doc-1", institution=None, country=None))

    assert repo.list("tenant-a", institution="Universidad Nacional") == []
    assert repo.list("tenant-a", country="Peru") == []


def test_document_count_is_tenant_scoped(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    repo.save(_document("doc-1", tenant_id="tenant-a"))
    repo.save(_document("doc-2", tenant_id="tenant-a"))
    repo.save(_document("doc-3", tenant_id="tenant-b"))

    assert repo.count("tenant-a") == 2
    assert repo.count("tenant-b") == 1
    assert repo.count("tenant-c") == 0


def test_chunk_delete_by_document_and_tenant_count(session) -> None:
    documents = SqlAlchemyDocumentRepository(session)
    chunks = SqlAlchemyChunkRepository(session)
    documents.save(_document("doc-1", tenant_id="tenant-a"))
    documents.save(_document("doc-2", tenant_id="tenant-b"))
    chunks.save_all([_chunk(1, "doc-1"), _chunk(2, "doc-2")])

    assert chunks.count_for_tenant("tenant-a") == 1
    assert chunks.count_for_tenant("tenant-b") == 1

    chunks.delete_by_document("doc-1")

    assert chunks.by_document("doc-1") == []
    assert chunks.count_for_tenant("tenant-a") == 0
    assert chunks.count_for_tenant("tenant-b") == 1
