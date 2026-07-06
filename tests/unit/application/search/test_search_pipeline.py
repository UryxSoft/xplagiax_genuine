from app.application.search.candidate_filter import CandidateFilter
from app.application.search.result_aggregator import ResultAggregator
from app.application.search.search_pipeline import SearchPipeline
from app.domain.entities.chunk import Chunk
from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.domain.value_objects.language import Language
from app.domain.value_objects.search_hit import SearchHit
from app.domain.value_objects.token_span import TokenSpan
from app.domain.value_objects.topic import Topic
from app.infrastructure.chunking.hybrid_chunker import HybridChunker
from app.infrastructure.chunking.word_token_counter import WordTokenCounter


class _FakeEmbeddingModel:
    def embed_query(self, text: str) -> EmbeddingVector:
        return EmbeddingVector(values=(float(len(text)), 0.0))


class _FakeLanguageDetector:
    def __init__(self, language: Language) -> None:
        self._language = language

    def detect(self, text: str) -> Language:
        return self._language


class _FakeTopicClassifier:
    def __init__(self, topic: Topic) -> None:
        self._topic = topic

    def classify(self, text: str) -> Topic:
        return self._topic


class _FakeDocumentRepository:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def ids_matching(self, tenant_id, language=None, topic=None) -> list[str]:
        return [
            r["id"]
            for r in self._rows
            if r["tenant_id"] == tenant_id
            and (language is None or r["language"] == language)
            and (topic is None or r["topic"] == topic)
        ]


class _FakeChunkRepository:
    def __init__(self, chunk_map: dict[str, list[int]], chunks: list[Chunk]) -> None:
        self._chunk_map = chunk_map
        self._by_id = {c.id: c for c in chunks}

    def ids_for_documents(self, document_ids: list[str]) -> list[int]:
        ids: list[int] = []
        for doc_id in document_ids:
            ids.extend(self._chunk_map.get(doc_id, []))
        return ids

    def by_ids(self, chunk_ids: list[int]) -> list[Chunk]:
        return [self._by_id[i] for i in chunk_ids if i in self._by_id]


class _FakeVectorIndex:
    def __init__(self, hits_by_allowlist_key: dict) -> None:
        self._hits = hits_by_allowlist_key

    def search(self, query, k, allowlist=None):
        key = frozenset(allowlist) if allowlist is not None else None
        return self._hits.get(key, [])[:k]


def _chunk(chunk_id: int, document_id: str) -> Chunk:
    return Chunk(id=chunk_id, document_id=document_id, text="x", span=TokenSpan(start=0, end=10), order=0)


def _build_pipeline(vector_index, document_rows, chunk_map, chunks, language, topic) -> SearchPipeline:
    candidate_filter = CandidateFilter(_FakeDocumentRepository(document_rows), _FakeChunkRepository(chunk_map, chunks))
    aggregator = ResultAggregator(_FakeChunkRepository(chunk_map, chunks))
    return SearchPipeline(
        chunker=HybridChunker(WordTokenCounter(), min_tokens=5, max_tokens=20, overlap_ratio=0.0),
        embedding_model=_FakeEmbeddingModel(),
        language_detector=_FakeLanguageDetector(language),
        topic_classifier=_FakeTopicClassifier(topic),
        candidate_filter=candidate_filter,
        vector_index=vector_index,
        result_aggregator=aggregator,
    )


def test_search_returns_aggregated_matches() -> None:
    rows = [{"id": "doc-1", "tenant_id": "tenant-a", "language": "es", "topic": "Ingenieria"}]
    chunk_map = {"doc-1": [10, 11]}
    chunks = [_chunk(10, "doc-1"), _chunk(11, "doc-1")]
    allowlist_key = frozenset({10, 11})
    vector_index = _FakeVectorIndex({allowlist_key: [SearchHit(chunk_id=10, score=0.9)]})

    pipeline = _build_pipeline(
        vector_index, rows, chunk_map, chunks,
        Language(code="es", confidence=0.9), Topic(domain="Ingenieria", confidence=0.9),
    )

    results = pipeline.search("un texto de prueba con contenido academico relevante", tenant_id="tenant-a")

    assert len(results) == 1
    assert results[0].document_id == "doc-1"


def test_search_returns_empty_when_filter_matches_nothing() -> None:
    rows = [{"id": "doc-1", "tenant_id": "tenant-a", "language": "en", "topic": "Medicina"}]
    vector_index = _FakeVectorIndex({})

    pipeline = _build_pipeline(
        vector_index, rows, {}, [],
        Language(code="es", confidence=0.9), Topic(domain="Ingenieria", confidence=0.9),
    )

    results = pipeline.search("texto que no coincide con ningun idioma o tema indexado", tenant_id="tenant-a")

    assert results == []


def test_search_returns_empty_for_empty_input_text() -> None:
    vector_index = _FakeVectorIndex({})
    pipeline = _build_pipeline(
        vector_index, [], {}, [], Language(code="es", confidence=0.9), Topic(domain="X", confidence=0.9)
    )

    assert pipeline.search("   ", tenant_id="tenant-a") == []
