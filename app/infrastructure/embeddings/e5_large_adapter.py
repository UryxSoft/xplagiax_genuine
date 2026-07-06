"""Adapter for intfloat/multilingual-e5-large (RF-09, ADR-003 default profile).

e5 models are trained with asymmetric "query: " / "passage: " prefixes and
expect L2-normalized output for cosine similarity via inner product
(docs/RESEARCH.md #1 length-renormalization discussion applies at the
TurboVec layer; here we just follow the model's own training convention).
"""

from __future__ import annotations

from app.domain.value_objects.embedding_vector import EmbeddingVector

_DEFAULT_MODEL_NAME = "intfloat/multilingual-e5-large"
_DEFAULT_DIMENSION = 1024


class E5LargeAdapter:
    """Wraps sentence-transformers around the e5-large multilingual model."""

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL_NAME,
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        from sentence_transformers import SentenceTransformer  # deferred: heavy optional import

        self._model_name = model_name
        self._batch_size = batch_size
        self._encoder = SentenceTransformer(model_name, device=device)
        self._dimension = self._encoder.get_sentence_embedding_dimension()

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return self._model_name

    def embed_passages(self, texts: list[str]) -> list[EmbeddingVector]:
        prefixed = [f"passage: {text}" for text in texts]
        return self._encode(prefixed)

    def embed_query(self, text: str) -> EmbeddingVector:
        return self._encode([f"query: {text}"])[0]

    def _encode(self, prefixed_texts: list[str]) -> list[EmbeddingVector]:
        if not prefixed_texts:
            return []
        vectors = self._encoder.encode(
            prefixed_texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [EmbeddingVector(values=tuple(float(x) for x in vector)) for vector in vectors]
