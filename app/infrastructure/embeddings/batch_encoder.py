"""SIMD-aware batching wrapper around an EmbeddingModel (ADR sect 14/6).

Groups cache misses into fixed-size batches before calling the model, so
the underlying encoder (e.g. sentence-transformers) always sees
consistent, throughput-friendly batch sizes regardless of how many
passages were already cached.
"""

from __future__ import annotations

from app.domain.ports.embedding_model import EmbeddingModel
from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.infrastructure.embeddings.embedding_cache import EmbeddingCache

_PASSAGE_NAMESPACE = "passage"
_QUERY_NAMESPACE = "query"


class BatchEncoder:
    """Batches embedding calls and transparently caches results."""

    def __init__(
        self,
        model: EmbeddingModel,
        cache: EmbeddingCache | None = None,
        batch_size: int = 32,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self._model = model
        self._cache = cache
        self._batch_size = batch_size

    def encode_passages(self, texts: list[str]) -> list[EmbeddingVector]:
        results: list[EmbeddingVector | None] = [None] * len(texts)
        miss_indices: list[int] = []
        miss_texts: list[str] = []

        for i, text in enumerate(texts):
            cached = self._cache.get(text, _PASSAGE_NAMESPACE) if self._cache is not None else None
            if cached is not None:
                results[i] = cached
            else:
                miss_indices.append(i)
                miss_texts.append(text)

        for start in range(0, len(miss_texts), self._batch_size):
            batch_indices = miss_indices[start : start + self._batch_size]
            batch_texts = miss_texts[start : start + self._batch_size]
            vectors = self._model.embed_passages(batch_texts)
            for idx, text, vector in zip(batch_indices, batch_texts, vectors):
                results[idx] = vector
                if self._cache is not None:
                    self._cache.put(text, vector, _PASSAGE_NAMESPACE)

        return [v for v in results if v is not None]

    def encode_query(self, text: str) -> EmbeddingVector:
        if self._cache is not None:
            cached = self._cache.get(text, _QUERY_NAMESPACE)
            if cached is not None:
                return cached

        vector = self._model.embed_query(text)
        if self._cache is not None:
            self._cache.put(text, vector, _QUERY_NAMESPACE)
        return vector
