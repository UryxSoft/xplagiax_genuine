from app.infrastructure.parsers.text_normalizer import TextNormalizer


def test_removes_page_numbers() -> None:
    markdown = "Intro text\n\n42\n\nMore body text"
    result = TextNormalizer().normalize(markdown, page_count=1)
    assert "42" not in result.split("\n")


def test_removes_repeated_header_across_pages() -> None:
    header = "Universidad Nacional - Facultad de Ingenieria"
    pages = [f"{header}\nContenido pagina {i}\n" for i in range(1, 6)]
    markdown = "\n".join(pages)

    result = TextNormalizer().normalize(markdown, page_count=5)

    assert header not in result
    assert "Contenido pagina 1" in result
    assert "Contenido pagina 5" in result


def test_collapses_excess_blank_lines() -> None:
    markdown = "Line one\n\n\n\n\nLine two"
    result = TextNormalizer().normalize(markdown, page_count=1)
    assert "\n\n\n" not in result


def test_single_page_document_keeps_all_body_lines() -> None:
    markdown = "Unique content that should never be treated as a repeated header"
    result = TextNormalizer().normalize(markdown, page_count=1)
    assert result == markdown
