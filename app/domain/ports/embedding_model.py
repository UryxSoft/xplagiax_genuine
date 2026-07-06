"""Port for embedding generation (ADR-003: TurboVec never generates embeddings).

Query and passage encoding are separate methods because asymmetric
embedding models (the e5 family) require different text prefixes
("query: " vs "passage: ") for correct retrieval quality -- collapsing
them into one `embed(text)` method would silently degrade recall for any
adapter built on such a model. Symmetric models (e.g. BGE-M3) simply
implement both methods identically.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.value_objects.embedding_vector import EmbeddingVector


class EmbeddingModel(Protocol):
    """Produces dense vectors for search queries and indexed passages."""

    @property
    def dimension(self) -> int:
        ...

    @property
    def name(self) -> str:
        ...

    def embed_passages(self, texts: list[str]) -> list[EmbeddingVector]:
        ...

    def embed_query(self, text: str) -> EmbeddingVector:
        ...
