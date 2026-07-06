import pytest
from pydantic import ValidationError

from app.domain.value_objects.pdf_source import PdfSource


def test_valid_pdf_source() -> None:
    source = PdfSource(filename="tesis.pdf", path="/data/tesis.pdf", pages=10, mime="application/pdf", size_bytes=1024)
    assert source.pages == 10


def test_rejects_non_pdf_mime() -> None:
    with pytest.raises(ValidationError):
        PdfSource(filename="x.exe", path="/data/x.exe", pages=1, mime="application/x-msdownload", size_bytes=10)


def test_rejects_oversized_file() -> None:
    with pytest.raises(ValidationError):
        PdfSource(
            filename="big.pdf",
            path="/data/big.pdf",
            pages=1,
            mime="application/pdf",
            size_bytes=300 * 1024 * 1024,
        )


def test_is_frozen() -> None:
    source = PdfSource(filename="a.pdf", path="/a.pdf", pages=1, mime="application/pdf", size_bytes=10)
    with pytest.raises(ValidationError):
        source.pages = 5
