"""Anti-corruption layer around Microsoft MarkItDown (RF-03)."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


class MarkItDownResult(NamedTuple):
    markdown: str
    pages: int


class MarkItDownAdapter:
    """Wraps the `markitdown` library behind a narrow, stable interface.

    The domain and pipeline never import `markitdown` directly: if the
    library's API changes, only this adapter needs to change.
    """

    def __init__(self) -> None:
        from markitdown import MarkItDown  # deferred: heavy optional import

        self._converter = MarkItDown()

    def convert(self, pdf_path: Path) -> MarkItDownResult:
        result = self._converter.convert(str(pdf_path))
        markdown: str = result.text_content or ""
        pages = self._count_pages(pdf_path)
        return MarkItDownResult(markdown=markdown, pages=pages)

    @staticmethod
    def _count_pages(pdf_path: Path) -> int:
        """Counts pages via the PDF's own object markers.

        MarkItDown does not report a page count; page boundaries are only
        needed for scanned-PDF density heuristics and TokenSpan.page, so a
        lightweight structural count (no full parse) is sufficient here.
        """
        from pypdf import PdfReader  # deferred: only needed for page counting

        return len(PdfReader(str(pdf_path)).pages)
