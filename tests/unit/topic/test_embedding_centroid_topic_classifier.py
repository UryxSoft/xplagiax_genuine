import pytest

from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.infrastructure.topic.embedding_centroid_topic_classifier import (
    EmbeddingCentroidTopicClassifier,
)


class _FakeEmbeddingModel:
    """Maps specific known strings to specific known vectors so cosine
    similarity outcomes are fully predictable."""

    def __init__(self, vectors_by_text: dict[str, tuple[float, ...]]) -> None:
        self._vectors_by_text = vectors_by_text

    def embed_passages(self, texts: list[str]) -> list[EmbeddingVector]:
        return [EmbeddingVector(values=self._vectors_by_text[t]) for t in texts]

    def embed_query(self, text: str) -> EmbeddingVector:
        return EmbeddingVector(values=self._vectors_by_text[text])


def test_classifies_to_nearest_centroid() -> None:
    model = _FakeEmbeddingModel(
        {
            "seed engineering": (1.0, 0.0),
            "seed medicine": (0.0, 1.0),
            "query about engineering": (0.9, 0.1),
        }
    )
    classifier = EmbeddingCentroidTopicClassifier.from_seed_texts(
        model, {"Ingenieria": ["seed engineering"], "Medicina": ["seed medicine"]}
    )

    topic = classifier.classify("query about engineering")

    assert topic.domain == "Ingenieria"
    assert 0.0 <= topic.confidence <= 1.0


def test_averages_multiple_seed_texts_into_one_centroid() -> None:
    model = _FakeEmbeddingModel(
        {
            "seed a": (1.0, 0.0),
            "seed b": (0.0, 1.0),  # average with seed a -> (0.5, 0.5)
            "query": (0.5, 0.5),
        }
    )
    classifier = EmbeddingCentroidTopicClassifier.from_seed_texts(
        model, {"Mixed": ["seed a", "seed b"]}
    )

    topic = classifier.classify("query")

    assert topic.domain == "Mixed"
    assert topic.confidence == pytest.approx(1.0, abs=1e-6)


def test_rejects_empty_centroids() -> None:
    model = _FakeEmbeddingModel({})
    with pytest.raises(ValueError):
        EmbeddingCentroidTopicClassifier(model, {})


def test_rejects_domain_with_no_seed_texts() -> None:
    model = _FakeEmbeddingModel({})
    with pytest.raises(ValueError):
        EmbeddingCentroidTopicClassifier.from_seed_texts(model, {"Empty": []})
