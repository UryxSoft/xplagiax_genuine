"""Complete in-memory fakes implementing the domain ports.

Shared by the API integration tests: they exercise the real application
services (IndexingPipeline, DocumentDeleter, SearchPipeline) over these
fakes, proving the full request->pipeline->storage loop without
PostgreSQL, TurboVec or a downloaded embedding model.
"""

from __future__ import annotations

import hashlib
import math

from app.domain.entities.chunk import Chunk
from app.domain.entities.document import Document
from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.domain.value_objects.language import Language
from app.domain.value_objects.search_hit import SearchHit
from app.domain.value_objects.sha256_hash import Sha256Hash
from app.domain.value_objects.topic import Topic


class InMemoryDocumentRepository:
    def __init__(self, documents: list[Document] | None = None) -> None:
        self._by_id: dict[str, Document] = {d.id: d for d in (documents or [])}

    def save(self, document: Document) -> None:
        self._by_id[document.id] = document

    def by_id(self, document_id: str) -> Document | None:
        return self._by_id.get(document_id)

    def by_hash(self, tenant_id: str, content_hash: Sha256Hash) -> Document | None:
        for document in self._by_id.values():
            if document.tenant_id == tenant_id and document.content_hash == content_hash:
                return document
        return None

    def list(
        self,
        tenant_id: str,
        language: str | None = None,
        topic: str | None = None,
        institution: str | None = None,
        country: str | None = None,
        page: int = 1,
    ) -> list[Document]:
        def matches(d: Document) -> bool:
            if d.tenant_id != tenant_id:
                return False
            if language is not None and (d.language is None or d.language.code != language):
                return False
            if topic is not None and (d.topic is None or d.topic.domain != topic):
                return False
            if institution is not None and (
                d.bibliography.institution is None
                or d.bibliography.institution.lower() != institution.lower()
            ):
                return False
            if country is not None and (
                d.bibliography.country is None
                or d.bibliography.country.lower() != country.lower()
            ):
                return False
            return True

        matching = sorted((d for d in self._by_id.values() if matches(d)), key=lambda d: d.id)
        page_size = 20
        return matching[(page - 1) * page_size : page * page_size]

    def ids_matching(
        self, tenant_id: str, language: str | None = None, topic: str | None = None
    ) -> list[str]:
        return [d.id for d in self.list(tenant_id, language=language, topic=topic, page=1)]

    def count(self, tenant_id: str) -> int:
        return sum(1 for d in self._by_id.values() if d.tenant_id == tenant_id)

    def delete(self, document_id: str) -> None:
        self._by_id.pop(document_id, None)


class InMemoryChunkRepository:
    def __init__(self, chunks: list[Chunk] | None = None) -> None:
        self._by_id: dict[int, Chunk] = {c.id: c for c in (chunks or [])}
        self._documents: InMemoryDocumentRepository | None = None

    def bind_documents(self, documents: InMemoryDocumentRepository) -> None:
        # count_for_tenant needs the document->tenant relation the SQL
        # implementation resolves with a join.
        self._documents = documents

    def save_all(self, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            self._by_id[chunk.id] = chunk

    def by_ids(self, chunk_ids: list[int]) -> list[Chunk]:
        return [self._by_id[i] for i in chunk_ids if i in self._by_id]

    def by_document(self, document_id: str) -> list[Chunk]:
        return sorted(
            (c for c in self._by_id.values() if c.document_id == document_id),
            key=lambda c: c.order,
        )

    def ids_for_documents(self, document_ids: list[str]) -> list[int]:
        wanted = set(document_ids)
        return [c.id for c in self._by_id.values() if c.document_id in wanted]

    def delete_by_document(self, document_id: str) -> None:
        self._by_id = {i: c for i, c in self._by_id.items() if c.document_id != document_id}

    def count_for_tenant(self, tenant_id: str) -> int:
        if self._documents is None:
            return 0
        tenant_docs = {
            d.id for d in self._documents._by_id.values() if d.tenant_id == tenant_id
        }
        return sum(1 for c in self._by_id.values() if c.document_id in tenant_docs)


class InMemoryVectorIndex:
    """Brute-force cosine search over stored vectors, allowlist-aware.

    write_to/from_file give it the same checkpoint surface as
    TurboVecRepository so the persistence-layer tests (VersionedIndexWriter,
    HotReloadingVectorIndex) can run real save/load cycles without the
    native library.
    """

    def __init__(self, dimension: int = 8) -> None:
        self._dimension = dimension
        self._vectors: dict[int, EmbeddingVector] = {}
        self._version = 0

    @classmethod
    def from_file(cls, path, dimension: int = 8) -> "InMemoryVectorIndex":
        import json

        instance = cls(dimension=dimension)
        data = json.loads(path.read_text(encoding="utf-8"))
        for chunk_id, values in data.items():
            instance._vectors[int(chunk_id)] = EmbeddingVector(values=tuple(values))
        return instance

    def write_to(self, path) -> None:
        import json

        payload = {str(i): list(v.values) for i, v in self._vectors.items()}
        path.write_text(json.dumps(payload), encoding="utf-8")

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def version(self) -> int:
        return self._version

    def add(self, chunk_ids: list[int], vectors: list[EmbeddingVector]) -> None:
        for chunk_id, vector in zip(chunk_ids, vectors):
            self._vectors[chunk_id] = vector

    def search(
        self, query: EmbeddingVector, k: int, allowlist: set[int] | None = None
    ) -> list[SearchHit]:
        candidates = (
            self._vectors.items()
            if allowlist is None
            else ((i, v) for i, v in self._vectors.items() if i in allowlist)
        )
        scored = [
            SearchHit(chunk_id=chunk_id, score=_cosine(query.values, vector.values))
            for chunk_id, vector in candidates
        ]
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]

    def remove(self, chunk_id: int) -> None:
        self._vectors.pop(chunk_id, None)

    def snapshot(self) -> None:
        self._version += 1

    def __len__(self) -> int:
        return len(self._vectors)


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    # identical vectors can give 1.0000000000000002 in floating point;
    # downstream signals require [0, 1]
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


class HashingEmbeddingModel:
    """Deterministic, content-sensitive fake embeddings.

    Word-level hashing into a small dense vector: identical texts map to
    identical vectors and overlapping texts to similar ones, which is
    enough signal for end-to-end index->search assertions.
    """

    def __init__(self, dimension: int = 8) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return "hashing-fake"

    def embed_passages(self, texts: list[str]) -> list[EmbeddingVector]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> EmbeddingVector:
        return self._embed(text)

    def _embed(self, text: str) -> EmbeddingVector:
        buckets = [0.0] * self._dimension
        for word in text.lower().split():
            digest = hashlib.md5(word.encode("utf-8")).digest()
            buckets[digest[0] % self._dimension] += 1.0
        norm = math.sqrt(sum(x * x for x in buckets)) or 1.0
        return EmbeddingVector(values=tuple(x / norm for x in buckets))


class StaticLanguageDetector:
    def __init__(self, code: str = "es", confidence: float = 0.95) -> None:
        self._language = Language(code=code, confidence=confidence)

    def detect(self, text: str) -> Language:
        return self._language


class StaticTopicClassifier:
    def __init__(self, domain: str = "Ingenieria", confidence: float = 0.9) -> None:
        self._topic = Topic(domain=domain, confidence=confidence)

    def classify(self, text: str) -> Topic:
        return self._topic
