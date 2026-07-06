from app.infrastructure.language.langdetect_adapter import LangDetectAdapter


def test_detects_spanish() -> None:
    adapter = LangDetectAdapter()
    result = adapter.detect(
        "La deteccion de plagio semantico utiliza embeddings vectoriales "
        "para comparar segmentos de texto entre documentos academicos."
    )
    assert result.code == "es"
    assert result.confidence > 0.5


def test_detects_english() -> None:
    adapter = LangDetectAdapter()
    result = adapter.detect(
        "Semantic plagiarism detection uses vector embeddings to compare "
        "text segments across academic documents in a large corpus."
    )
    assert result.code == "en"
    assert result.confidence > 0.5


def test_very_short_text_returns_default_with_zero_confidence() -> None:
    adapter = LangDetectAdapter()
    result = adapter.detect("ok")
    assert result.confidence == 0.0
