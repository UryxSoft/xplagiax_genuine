from pathlib import Path

from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata
from app.infrastructure.parsers.grobid_adapter import GrobidUnavailableError
from app.infrastructure.parsers.markitdown_adapter import MarkItDownResult
from app.infrastructure.parsers.pdf_parser_service import PdfParserService
from app.infrastructure.parsers.scanned_pdf_detector import ScannedPdfDetector
from app.infrastructure.parsers.text_normalizer import TextNormalizer


class _FakeMarkItDown:
    def __init__(self, result: MarkItDownResult) -> None:
        self._result = result

    def convert(self, pdf_path: Path) -> MarkItDownResult:
        return self._result


class _FakeGrobid:
    def __init__(self, metadata: BibliographicMetadata | None = None, raises: bool = False) -> None:
        self._metadata = metadata or BibliographicMetadata()
        self._raises = raises

    def extract_header(self, pdf_path: Path) -> BibliographicMetadata:
        if self._raises:
            raise GrobidUnavailableError("down")
        return self._metadata


def test_extract_combines_markitdown_and_grobid(tmp_path) -> None:
    markdown = "Universidad Nacional de Ingenieria\n\nCuerpo del documento con contenido relevante."
    service = PdfParserService(
        markitdown_adapter=_FakeMarkItDown(MarkItDownResult(markdown=markdown, pages=1)),
        grobid_adapter=_FakeGrobid(BibliographicMetadata(title="Tesis X", authors=("Ana Ruiz",))),
        normalizer=TextNormalizer(),
        scanned_detector=ScannedPdfDetector(min_chars_per_page=10),
    )

    result = service.extract(tmp_path / "doc.pdf")

    assert result.bibliography.title == "Tesis X"
    assert result.bibliography.authors == ("Ana Ruiz",)
    assert result.is_scanned is False


def test_falls_back_to_first_page_institution_when_grobid_has_none(tmp_path) -> None:
    markdown = "Universidad Nacional de Ingenieria\n\nContenido academico extenso y relevante aqui."
    service = PdfParserService(
        markitdown_adapter=_FakeMarkItDown(MarkItDownResult(markdown=markdown, pages=1)),
        grobid_adapter=_FakeGrobid(BibliographicMetadata()),  # institution=None
        normalizer=TextNormalizer(),
        scanned_detector=ScannedPdfDetector(min_chars_per_page=10),
    )

    result = service.extract(tmp_path / "doc.pdf")

    assert result.bibliography.institution == "Universidad Nacional de Ingenieria"


def test_grobid_unavailable_yields_null_metadata_not_a_crash(tmp_path) -> None:
    markdown = "Sin mencion de universidad aqui, solo texto plano de relleno."
    service = PdfParserService(
        markitdown_adapter=_FakeMarkItDown(MarkItDownResult(markdown=markdown, pages=1)),
        grobid_adapter=_FakeGrobid(raises=True),
        normalizer=TextNormalizer(),
        scanned_detector=ScannedPdfDetector(min_chars_per_page=10),
    )

    result = service.extract(tmp_path / "doc.pdf")

    assert result.bibliography.title is None
    assert result.bibliography.authors == ()


def test_detects_scanned_pdf(tmp_path) -> None:
    service = PdfParserService(
        markitdown_adapter=_FakeMarkItDown(MarkItDownResult(markdown="a", pages=5)),
        grobid_adapter=_FakeGrobid(),
        normalizer=TextNormalizer(),
        scanned_detector=ScannedPdfDetector(min_chars_per_page=200),
    )

    result = service.extract(tmp_path / "doc.pdf")

    assert result.is_scanned is True
