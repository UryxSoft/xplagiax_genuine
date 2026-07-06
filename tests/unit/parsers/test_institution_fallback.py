from app.infrastructure.parsers.institution_fallback import guess_institution


def test_finds_spanish_university_mention() -> None:
    markdown = "Tesis presentada en la\nUniversidad Nacional de Ingenieria\nLima, Peru"
    assert guess_institution(markdown) == "Universidad Nacional de Ingenieria"


def test_finds_english_university_mention() -> None:
    markdown = "A thesis submitted to\nUniversity of Cambridge\nDepartment of Engineering"
    result = guess_institution(markdown)
    assert result is not None
    assert "University of Cambridge" in result


def test_returns_none_when_no_institution_mentioned() -> None:
    markdown = "Just some random text with no academic affiliation at all."
    assert guess_institution(markdown) is None


def test_only_searches_first_page_budget() -> None:
    filler = "x " * 2000
    markdown = filler + "Universidad Nacional de Ingenieria"
    assert guess_institution(markdown) is None
