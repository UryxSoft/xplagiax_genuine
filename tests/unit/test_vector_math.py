import pytest

from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.utils.vector_math import cosine_similarity


def test_identical_vectors_have_similarity_one() -> None:
    v = EmbeddingVector(values=(1.0, 2.0, 3.0))
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_orthogonal_vectors_have_similarity_zero() -> None:
    a = EmbeddingVector(values=(1.0, 0.0))
    b = EmbeddingVector(values=(0.0, 1.0))
    assert cosine_similarity(a, b) == pytest.approx(0.0)


def test_opposite_vectors_have_similarity_negative_one() -> None:
    a = EmbeddingVector(values=(1.0, 0.0))
    b = EmbeddingVector(values=(-1.0, 0.0))
    assert cosine_similarity(a, b) == pytest.approx(-1.0)


def test_zero_vector_yields_zero_not_division_error() -> None:
    a = EmbeddingVector(values=(0.0, 0.0))
    b = EmbeddingVector(values=(1.0, 1.0))
    assert cosine_similarity(a, b) == 0.0


def test_dimension_mismatch_raises() -> None:
    a = EmbeddingVector(values=(1.0, 0.0))
    b = EmbeddingVector(values=(1.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        cosine_similarity(a, b)
