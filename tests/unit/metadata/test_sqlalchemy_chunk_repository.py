from app.domain.entities.chunk import Chunk
from app.domain.entities.document import Document
from app.domain.value_objects.pdf_source import PdfSource
from app.domain.value_objects.sha256_hash import Sha256Hash
from app.domain.value_objects.token_span import TokenSpan
from app.infrastructure.metadata.sqlalchemy_chunk_repository import SqlAlchemyChunkRepository
from app.infrastructure.metadata.sqlalchemy_document_repository import SqlAlchemyDocumentRepository


def _make_document(doc_id: str) -> Document:
    return Document(
        id=doc_id,
        tenant_id="tenant-a",
        source=PdfSource(filename="x.pdf", path="/x.pdf", pages=5, mime="application/pdf", size_bytes=10),
        content_hash=Sha256Hash.of(doc_id),
    )


def _make_chunk(chunk_id: int, document_id: str, order: int) -> Chunk:
    return Chunk(
        id=chunk_id,
        document_id=document_id,
        text=f"chunk text {chunk_id}",
        span=TokenSpan(start=order * 100, end=order * 100 + 50),
        order=order,
    )


def test_save_all_and_by_document_returns_in_order(session) -> None:
    SqlAlchemyDocumentRepository(session).save(_make_document("doc-1"))
    repo = SqlAlchemyChunkRepository(session)

    chunks = [_make_chunk(3, "doc-1", order=1), _make_chunk(1, "doc-1", order=0), _make_chunk(2, "doc-1", order=2)]
    repo.save_all(chunks)

    fetched = repo.by_document("doc-1")

    assert [c.order for c in fetched] == [0, 1, 2]
    assert [c.id for c in fetched] == [1, 3, 2]


def test_by_ids_fetches_requested_subset(session) -> None:
    SqlAlchemyDocumentRepository(session).save(_make_document("doc-1"))
    repo = SqlAlchemyChunkRepository(session)
    repo.save_all([_make_chunk(i, "doc-1", order=i) for i in range(5)])

    fetched = repo.by_ids([1, 3])

    assert {c.id for c in fetched} == {1, 3}


def test_by_document_empty_when_no_chunks(session) -> None:
    SqlAlchemyDocumentRepository(session).save(_make_document("doc-1"))
    repo = SqlAlchemyChunkRepository(session)

    assert repo.by_document("doc-1") == []


def test_by_ids_empty_list_returns_empty(session) -> None:
    repo = SqlAlchemyChunkRepository(session)
    assert repo.by_ids([]) == []


def test_save_all_empty_list_is_noop(session) -> None:
    repo = SqlAlchemyChunkRepository(session)
    repo.save_all([])  # must not raise
