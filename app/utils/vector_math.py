"""Shared vector arithmetic used by topic classification and reranking."""

from __future__ import annotations

import math

from app.domain.value_objects.embedding_vector import EmbeddingVector


def cosine_similarity(a: EmbeddingVector, b: EmbeddingVector) -> float:
    if a.dimension != b.dimension:
        raise ValueError(f"dimension mismatch: {a.dimension} vs {b.dimension}")

    dot = sum(x * y for x, y in zip(a.values, b.values))
    norm_a = math.sqrt(sum(x * x for x in a.values))
    norm_b = math.sqrt(sum(y * y for y in b.values))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
