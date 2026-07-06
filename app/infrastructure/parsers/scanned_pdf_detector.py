"""Heuristic detector for scanned (image-only) PDFs that need OCR fallback."""

from __future__ import annotations


class ScannedPdfDetector:
    """Flags a PDF as scanned when extracted text density is too low.

    A scanned PDF yields near-empty MarkItDown output (no embedded text
    layer). OCR is deliberately out of the critical path (ADR: MarkItDown
    only, OCR opt-in) so this is a signal for the caller to decide, not an
    automatic OCR trigger.
    """

    def __init__(self, min_chars_per_page: int = 200) -> None:
        self._min_chars_per_page = min_chars_per_page

    def is_scanned(self, markdown: str, page_count: int) -> bool:
        if page_count <= 0:
            return True
        avg_chars_per_page = len(markdown) / page_count
        return avg_chars_per_page < self._min_chars_per_page
