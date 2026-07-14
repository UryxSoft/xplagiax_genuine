from app.infrastructure.parsers.plain_text_normalizer import normalize_plain_text


def test_normalizes_windows_line_endings() -> None:
    assert normalize_plain_text("a\r\nb\rc") == "a\nb\nc"


def test_collapses_excess_blank_lines_but_keeps_paragraphs() -> None:
    assert normalize_plain_text("p1\n\n\n\n\np2") == "p1\n\np2"


def test_strips_trailing_spaces_and_outer_whitespace() -> None:
    assert normalize_plain_text("  line one   \nline two\t\n  ") == "line one\nline two"


def test_repeated_lines_survive() -> None:
    # Unlike the PDF TextNormalizer, repeated lines are body content here,
    # never running headers to strip.
    text = "estribillo\n\nestrofa\n\nestribillo"
    assert normalize_plain_text(text) == text


def test_empty_input_yields_empty_string() -> None:
    assert normalize_plain_text(" \n \n ") == ""
