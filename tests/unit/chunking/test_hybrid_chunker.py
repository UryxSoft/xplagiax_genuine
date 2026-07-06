from app.infrastructure.chunking.hybrid_chunker import HybridChunker
from app.infrastructure.chunking.word_token_counter import WordTokenCounter


def _make_paragraph(word_count: int, prefix: str) -> str:
    """Builds a single-sentence paragraph of exactly word_count+1 tokens
    (words + one trailing period) under WordTokenCounter."""
    words = [f"{prefix}{i}" for i in range(word_count)]
    return " ".join(words) + "."


def _chunker(min_tokens: int = 300, max_tokens: int = 500, overlap_ratio: float = 0.2) -> HybridChunker:
    return HybridChunker(
        token_counter=WordTokenCounter(),
        min_tokens=min_tokens,
        max_tokens=max_tokens,
        overlap_ratio=overlap_ratio,
    )


def test_empty_text_yields_no_segments() -> None:
    assert _chunker().chunk("") == []
    assert _chunker().chunk("   \n\n  ") == []


def test_short_multi_paragraph_text_fits_in_one_segment() -> None:
    paragraphs = [_make_paragraph(150, f"p{i}_") for i in range(3)]  # 151 tokens each, 453 total
    text = "\n\n".join(paragraphs)

    segments = _chunker().chunk(text)

    assert len(segments) == 1
    assert segments[0].order == 0
    for i in range(3):
        assert f"p{i}_0" in segments[0].text


def test_long_text_splits_into_bounded_overlapping_segments() -> None:
    paragraphs = [_make_paragraph(150, f"p{i}_") for i in range(5)]  # 151 tokens each, 755 total
    text = "\n\n".join(paragraphs)

    segments = _chunker(min_tokens=300, max_tokens=500, overlap_ratio=0.2).chunk(text)

    assert len(segments) == 2
    for segment in segments:
        token_count = segment.span.end - segment.span.start
        assert token_count <= 500

    # p2 ("p2_0" .. "p2_149") must appear in both segments -> overlap is real, not just adjacency
    assert "p2_0" in segments[0].text
    assert "p2_0" in segments[1].text

    # overlap means segment 2 starts before segment 1 ends
    assert segments[1].span.start < segments[0].span.end

    # order is sequential
    assert [s.order for s in segments] == [0, 1]


def test_oversized_single_sentence_is_hard_split() -> None:
    huge_paragraph = _make_paragraph(700, "w")  # 701 tokens, single sentence, no internal boundary
    segments = _chunker(min_tokens=300, max_tokens=500, overlap_ratio=0.0).chunk(huge_paragraph)

    assert len(segments) >= 2
    counter = WordTokenCounter()
    for segment in segments:
        assert counter.count(segment.text) <= 500


def test_zero_overlap_produces_contiguous_non_duplicated_segments() -> None:
    paragraphs = [_make_paragraph(150, f"p{i}_") for i in range(5)]
    text = "\n\n".join(paragraphs)

    segments = _chunker(min_tokens=300, max_tokens=500, overlap_ratio=0.0).chunk(text)

    for first, second in zip(segments, segments[1:]):
        assert second.span.start == first.span.end


def test_rejects_invalid_bounds() -> None:
    import pytest

    with pytest.raises(ValueError):
        HybridChunker(WordTokenCounter(), min_tokens=500, max_tokens=300)
    with pytest.raises(ValueError):
        HybridChunker(WordTokenCounter(), min_tokens=100, max_tokens=200, overlap_ratio=1.0)
