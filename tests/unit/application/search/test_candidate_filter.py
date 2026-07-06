from app.application.search.candidate_filter import CandidateFilter
from app.domain.value_objects.language import Language
from app.domain.value_objects.topic import Topic


class _FakeDocumentRepository:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows  # each: {id, tenant_id, language, topic}

    def ids_matching(self, tenant_id, language=None, topic=None) -> list[str]:
        return [
            r["id"]
            for r in self._rows
            if r["tenant_id"] == tenant_id
            and (language is None or r["language"] == language)
            and (topic is None or r["topic"] == topic)
        ]


class _FakeChunkRepository:
    def __init__(self, chunk_ids_by_document: dict[str, list[int]]) -> None:
        self._by_doc = chunk_ids_by_document

    def ids_for_documents(self, document_ids: list[str]) -> list[int]:
        ids: list[int] = []
        for doc_id in document_ids:
            ids.extend(self._by_doc.get(doc_id, []))
        return ids


def _make_filter(rows, chunk_map, topic_threshold=0.5) -> CandidateFilter:
    return CandidateFilter(
        _FakeDocumentRepository(rows), _FakeChunkRepository(chunk_map), topic_threshold
    )


def test_no_language_or_topic_means_unrestricted() -> None:
    cf = _make_filter([], {})
    assert cf.build_allowlist("tenant-a", language=None, topic=None) is None


def test_filters_by_language_and_topic() -> None:
    rows = [
        {"id": "doc-1", "tenant_id": "tenant-a", "language": "es", "topic": "Ingenieria"},
        {"id": "doc-2", "tenant_id": "tenant-a", "language": "en", "topic": "Ingenieria"},
    ]
    chunk_map = {"doc-1": [1, 2], "doc-2": [3, 4]}
    cf = _make_filter(rows, chunk_map)

    allowlist = cf.build_allowlist(
        "tenant-a", Language(code="es", confidence=0.99), Topic(domain="Ingenieria", confidence=0.9)
    )

    assert allowlist == {1, 2}


def test_low_confidence_topic_is_dropped_from_filter() -> None:
    rows = [
        {"id": "doc-1", "tenant_id": "tenant-a", "language": "es", "topic": "Ingenieria"},
        {"id": "doc-2", "tenant_id": "tenant-a", "language": "es", "topic": "Medicina"},
    ]
    chunk_map = {"doc-1": [1], "doc-2": [2]}
    cf = _make_filter(rows, chunk_map, topic_threshold=0.5)

    # topic confidence below threshold -> topic filter relaxed, language filter kept
    allowlist = cf.build_allowlist(
        "tenant-a", Language(code="es", confidence=0.99), Topic(domain="Ingenieria", confidence=0.2)
    )

    assert allowlist == {1, 2}


def test_no_matching_documents_returns_empty_set_not_none() -> None:
    rows = [{"id": "doc-1", "tenant_id": "tenant-a", "language": "en", "topic": "Medicina"}]
    cf = _make_filter(rows, {"doc-1": [1]})

    allowlist = cf.build_allowlist(
        "tenant-a", Language(code="es", confidence=0.9), Topic(domain="Ingenieria", confidence=0.9)
    )

    assert allowlist == set()


def test_tenant_isolation() -> None:
    rows = [{"id": "doc-1", "tenant_id": "tenant-b", "language": "es", "topic": "Ingenieria"}]
    cf = _make_filter(rows, {"doc-1": [1]})

    allowlist = cf.build_allowlist(
        "tenant-a", Language(code="es", confidence=0.9), Topic(domain="Ingenieria", confidence=0.9)
    )

    assert allowlist == set()
