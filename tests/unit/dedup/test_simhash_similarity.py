import pytest

from app.infrastructure.dedup.simhash_similarity import simhash, simhash_similarity


def test_identical_text_has_similarity_one() -> None:
    text = "la deteccion de plagio semantico usa embeddings vectoriales"
    assert simhash_similarity(text, text) == pytest.approx(1.0)


def test_very_different_text_has_lower_similarity() -> None:
    a = "la deteccion de plagio semantico usa embeddings vectoriales para comparar"
    b = "el clima de hoy en la ciudad sera soleado con temperaturas templadas"
    assert simhash_similarity(a, b) < 1.0


def test_empty_text_produces_zero_fingerprint() -> None:
    assert simhash("") == 0


def test_similarity_is_symmetric() -> None:
    a = "texto de prueba academico"
    b = "otro texto completamente distinto sobre clima"
    assert simhash_similarity(a, b) == pytest.approx(simhash_similarity(b, a))
