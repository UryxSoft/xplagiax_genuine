from app.infrastructure.dedup.exact_match import exact_ngram_overlap


def test_identical_text_has_full_overlap() -> None:
    text = "uno dos tres cuatro cinco seis siete ocho nueve diez"
    assert exact_ngram_overlap(text, text) == 1.0


def test_no_overlap_with_unrelated_text() -> None:
    query = "uno dos tres cuatro cinco seis siete ocho"
    candidate = "clima soleado templado ciudad lluvia viento nublado frio"
    assert exact_ngram_overlap(query, candidate) == 0.0


def test_partial_verbatim_copy_detected() -> None:
    shared = "esta frase exacta aparece copiada literalmente en ambos documentos"
    query = f"introduccion. {shared}. conclusion del documento uno."
    candidate = f"resumen. {shared}. conclusion del documento dos, distinta."
    overlap = exact_ngram_overlap(query, candidate, ngram_size=5)
    assert overlap > 0.0


def test_empty_query_yields_zero() -> None:
    assert exact_ngram_overlap("", "algun contenido de referencia") == 0.0
