from app.application.ranking.reranker import Reranker
from app.domain.entities.chunk import Chunk
from app.domain.entities.document import Document
from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata
from app.domain.value_objects.language import Language
from app.domain.value_objects.match_result import MatchResult
from app.domain.value_objects.pdf_source import PdfSource
from app.domain.value_objects.search_hit import SearchHit
from app.domain.value_objects.sha256_hash import Sha256Hash
from app.domain.value_objects.token_span import TokenSpan
from app.domain.value_objects.topic import Topic
from app.infrastructure.metadata.institution_normalizer import InstitutionNormalizer


class _FakeChunkRepository:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._by_id = {c.id: c for c in chunks}

    def by_ids(self, chunk_ids: list[int]) -> list[Chunk]:
        return [self._by_id[i] for i in chunk_ids if i in self._by_id]


def _chunk(chunk_id: int, text: str) -> Chunk:
    return Chunk(id=chunk_id, document_id="doc-1", text=text, span=TokenSpan(start=0, end=10), order=0)


def _document(
    language: Language | None = None,
    topic: Topic | None = None,
    institution: str | None = None,
) -> Document:
    return Document(
        id="doc-1",
        tenant_id="tenant-a",
        source=PdfSource(filename="x.pdf", path="/x.pdf", pages=10, mime="application/pdf", size_bytes=10),
        content_hash=Sha256Hash.of("doc-1"),
        bibliography=BibliographicMetadata(institution=institution),
        language=language,
        topic=topic,
    )


def _match(chunk_ids: list[int], score: float = 0.9) -> MatchResult:
    hits = tuple(SearchHit(chunk_id=i, score=score) for i in chunk_ids)
    return MatchResult(document_id="doc-1", chunk_hits=hits, average_score=score, max_score=score, best_hit=hits[0])


def test_embedding_signal_reuses_match_max_score() -> None:
    chunks = [_chunk(1, "contenido de ejemplo")]
    reranker = Reranker(_FakeChunkRepository(chunks))

    signals = reranker.compute_signals(
        _match([1], score=0.87), "texto de consulta", None, None, _document()
    )

    assert signals.embedding == 0.87


def test_language_and_topic_match_are_binary() -> None:
    chunks = [_chunk(1, "contenido")]
    reranker = Reranker(_FakeChunkRepository(chunks))
    document = _document(language=Language(code="es", confidence=0.9), topic=Topic(domain="Ingenieria", confidence=0.9))

    matching_signals = reranker.compute_signals(
        _match([1]), "consulta", Language(code="es", confidence=0.9), Topic(domain="Ingenieria", confidence=0.9), document
    )
    mismatched_signals = reranker.compute_signals(
        _match([1]), "consulta", Language(code="en", confidence=0.9), Topic(domain="Medicina", confidence=0.9), document
    )

    assert matching_signals.language == 1.0
    assert matching_signals.topic == 1.0
    assert mismatched_signals.language == 0.0
    assert mismatched_signals.topic == 0.0


def test_language_signal_is_none_when_either_side_unknown() -> None:
    chunks = [_chunk(1, "contenido")]
    reranker = Reranker(_FakeChunkRepository(chunks))

    signals = reranker.compute_signals(_match([1]), "consulta", None, None, _document())

    assert signals.language is None
    assert signals.topic is None


def test_minhash_simhash_exact_reflect_verbatim_overlap() -> None:
    shared_text = "esta es una frase larga que aparece copiada de forma literal en ambos"
    chunks = [_chunk(1, shared_text)]
    reranker = Reranker(_FakeChunkRepository(chunks))

    signals = reranker.compute_signals(_match([1]), shared_text, None, None, _document())

    assert signals.minhash == 1.0
    assert signals.simhash == 1.0
    assert signals.exact == 1.0


def test_entity_match_uses_institution_fallback_and_normalizer() -> None:
    chunks = [_chunk(1, "contenido")]
    reranker = Reranker(_FakeChunkRepository(chunks), InstitutionNormalizer())
    document = _document(institution="Universidad Nacional de Ingenieria")

    query_text = "Tesis presentada en la\nUniversidad Nacional de Ingenieria\nLima, Peru"
    signals = reranker.compute_signals(_match([1]), query_text, None, None, document)

    assert signals.entity == 1.0


def test_entity_match_is_none_when_query_has_no_institution_mention() -> None:
    chunks = [_chunk(1, "contenido")]
    reranker = Reranker(_FakeChunkRepository(chunks))
    document = _document(institution="Universidad Nacional de Ingenieria")

    signals = reranker.compute_signals(_match([1]), "texto sin ninguna mencion institucional", None, None, document)

    assert signals.entity is None


def test_entity_match_is_none_when_document_has_no_institution() -> None:
    chunks = [_chunk(1, "contenido")]
    reranker = Reranker(_FakeChunkRepository(chunks))
    document = _document(institution=None)

    query_text = "Tesis de la Universidad Nacional de Ingenieria"
    signals = reranker.compute_signals(_match([1]), query_text, None, None, document)

    assert signals.entity is None
