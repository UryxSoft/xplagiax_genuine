from app.infrastructure.dedup.shingles import word_shingles


def test_produces_overlapping_ngrams() -> None:
    result = word_shingles("a b c d", size=2)
    assert result == {"a b", "b c", "c d"}


def test_short_text_yields_single_shingle() -> None:
    result = word_shingles("only two", size=5)
    assert result == {"only two"}


def test_empty_text_yields_no_shingles() -> None:
    assert word_shingles("", size=3) == set()
    assert word_shingles("   ", size=3) == set()
