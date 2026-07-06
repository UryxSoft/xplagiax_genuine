import pytest

from app.infrastructure.dedup.minhash_similarity import minhash_similarity


def test_identical_text_has_similarity_one() -> None:
    text = "la deteccion de plagio semantico usa embeddings vectoriales para comparar textos"
    assert minhash_similarity(text, text) == pytest.approx(1.0)


def test_completely_different_text_has_low_similarity() -> None:
    a = "la deteccion de plagio semantico usa embeddings vectoriales para comparar"
    b = "el clima de hoy en la ciudad sera soleado con temperaturas templadas"
    assert minhash_similarity(a, b) < 0.3


def test_partial_overlap_has_intermediate_similarity() -> None:
    a = "la deteccion de plagio semantico usa embeddings vectoriales para comparar textos academicos"
    b = "la deteccion de plagio semantico usa modelos estadisticos para clasificar textos juridicos"
    similarity = minhash_similarity(a, b)
    assert 0.0 < similarity < 1.0


def test_empty_text_yields_zero() -> None:
    assert minhash_similarity("", "algo de contenido") == 0.0
    assert minhash_similarity("algo de contenido", "") == 0.0
