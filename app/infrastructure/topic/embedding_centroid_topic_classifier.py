"""Embeddings-based topic classification (RF-07: nearest-centroid, not keywords).

Seed texts for each domain are embedded as passages (`embed_passages`) and
averaged into a centroid; incoming text is embedded as a query
(`embed_query`) and matched against centroids by cosine similarity. This
mirrors the asymmetric query/passage pairing e5-family models are trained
for, rather than comparing text of the same kind on both sides.

The centroids used here must come from a real labeled corpus in
production (embed a representative sample per academic domain and
average); `from_seed_texts` with a handful of example sentences is a
starter/testing convenience, not a substitute for that.
"""

from __future__ import annotations

from app.domain.ports.embedding_model import EmbeddingModel
from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.domain.value_objects.topic import Topic
from app.utils.vector_math import cosine_similarity


class EmbeddingCentroidTopicClassifier:
    def __init__(self, embedding_model: EmbeddingModel, centroids: dict[str, EmbeddingVector]) -> None:
        if not centroids:
            raise ValueError("centroids must not be empty")
        self._model = embedding_model
        self._centroids = centroids

    @classmethod
    def from_seed_texts(
        cls, embedding_model: EmbeddingModel, seed_texts: dict[str, list[str]]
    ) -> "EmbeddingCentroidTopicClassifier":
        centroids: dict[str, EmbeddingVector] = {}
        for domain, texts in seed_texts.items():
            if not texts:
                raise ValueError(f"domain '{domain}' has no seed texts")
            vectors = embedding_model.embed_passages(texts)
            centroids[domain] = cls._average(vectors)
        return cls(embedding_model, centroids)

    def classify(self, text: str) -> Topic:
        query_vector = self._model.embed_query(text)

        scored = [
            (domain, cosine_similarity(query_vector, centroid))
            for domain, centroid in self._centroids.items()
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        best_domain, best_similarity = scored[0]

        confidence = max(0.0, min(1.0, (best_similarity + 1.0) / 2.0))
        return Topic(domain=best_domain, confidence=confidence)

    @staticmethod
    def _average(vectors: list[EmbeddingVector]) -> EmbeddingVector:
        dim = vectors[0].dimension
        sums = [0.0] * dim
        for vector in vectors:
            for i, value in enumerate(vector.values):
                sums[i] += value
        return EmbeddingVector(values=tuple(s / len(vectors) for s in sums))
