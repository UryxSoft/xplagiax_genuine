import pytest

from app.domain.entities.document import Document
from app.domain.entities.document_status import DocumentStatus
from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata
from app.domain.value_objects.language import Language
from app.domain.value_objects.pdf_source import PdfSource
from app.domain.value_objects.sha256_hash import Sha256Hash
from app.domain.value_objects.topic import Topic
from app.infrastructure.metadata.sqlalchemy_document_repository import SqlAlchemyDocumentRepository


def _make_document(doc_id: str = "doc-1", tenant_id: str = "tenant-a", text: str = "content") -> Document:
    return Document(
        id=doc_id,
        tenant_id=tenant_id,
        source=PdfSource(filename="tesis.pdf", path="/data/tesis.pdf", pages=50, mime="application/pdf", size_bytes=1000),
        content_hash=Sha256Hash.of(text),
        bibliography=BibliographicMetadata(title="Tesis X", authors=("Ana Ruiz",), institution="Universidad X"),
        language=Language(code="es", confidence=0.99),
        topic=Topic(domain="Ingenieria", confidence=0.8),
        status=DocumentStatus.INDEXED,
    )


def test_save_and_by_id_roundtrip(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    document = _make_document()

    repo.save(document)
    fetched = repo.by_id("doc-1")

    assert fetched is not None
    assert fetched.id == "doc-1"
    assert fetched.bibliography.title == "Tesis X"
    assert fetched.bibliography.authors == ("Ana Ruiz",)
    assert fetched.language.code == "es"
    assert fetched.topic.domain == "Ingenieria"
    assert fetched.status == DocumentStatus.INDEXED


def test_by_id_returns_none_when_missing(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    assert repo.by_id("does-not-exist") is None


def test_by_hash_finds_document_within_tenant(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    document = _make_document(text="unique content")
    repo.save(document)

    found = repo.by_hash("tenant-a", Sha256Hash.of("unique content"))

    assert found is not None
    assert found.id == "doc-1"


def test_by_hash_does_not_leak_across_tenants(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    document = _make_document(doc_id="doc-1", tenant_id="tenant-a", text="shared text")
    repo.save(document)

    found = repo.by_hash("tenant-b", Sha256Hash.of("shared text"))

    assert found is None


def test_list_filters_by_tenant_language_and_topic(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    repo.save(_make_document(doc_id="doc-1", tenant_id="tenant-a", text="a"))
    repo.save(_make_document(doc_id="doc-2", tenant_id="tenant-a", text="b"))
    other = _make_document(doc_id="doc-3", tenant_id="tenant-b", text="c")
    repo.save(other)

    results = repo.list(tenant_id="tenant-a")
    assert {d.id for d in results} == {"doc-1", "doc-2"}

    results = repo.list(tenant_id="tenant-a", language="es", topic="Ingenieria")
    assert {d.id for d in results} == {"doc-1", "doc-2"}

    results = repo.list(tenant_id="tenant-a", topic="Medicina")
    assert results == []


def test_delete_removes_document(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    repo.save(_make_document())

    repo.delete("doc-1")

    assert repo.by_id("doc-1") is None


def test_delete_missing_document_is_a_noop(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    repo.delete("does-not-exist")  # must not raise


def test_list_rejects_page_below_one(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    with pytest.raises(ValueError):
        repo.list(tenant_id="tenant-a", page=0)


def test_document_without_language_or_topic_roundtrips_as_none(session) -> None:
    repo = SqlAlchemyDocumentRepository(session)
    document = Document(
        id="doc-null",
        tenant_id="tenant-a",
        source=PdfSource(filename="x.pdf", path="/x.pdf", pages=1, mime="application/pdf", size_bytes=10),
        content_hash=Sha256Hash.of("no lang no topic"),
    )
    repo.save(document)

    fetched = repo.by_id("doc-null")

    assert fetched.language is None
    assert fetched.topic is None
    assert fetched.bibliography.institution is None
