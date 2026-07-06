"""Orchestrates MarkItDown + GROBID + normalization into one ExtractedDocument.

Implements the `DocumentParser` port. This is the only class the
application layer depends on for extraction (app/domain/ports/document_parser.py).
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata
from app.domain.value_objects.extracted_document import ExtractedDocument
from app.infrastructure.parsers.grobid_adapter import GrobidAdapter, GrobidUnavailableError
from app.infrastructure.parsers.institution_fallback import guess_institution
from app.infrastructure.parsers.markitdown_adapter import MarkItDownAdapter
from app.infrastructure.parsers.scanned_pdf_detector import ScannedPdfDetector
from app.infrastructure.parsers.text_normalizer import TextNormalizer

logger = logging.getLogger(__name__)


class PdfParserService:
    """Extracts normalized text and best-effort bibliographic metadata from a PDF."""

    def __init__(
        self,
        markitdown_adapter: MarkItDownAdapter,
        grobid_adapter: GrobidAdapter | None,
        normalizer: TextNormalizer,
        scanned_detector: ScannedPdfDetector,
    ) -> None:
        self._markitdown = markitdown_adapter
        self._grobid = grobid_adapter
        self._normalizer = normalizer
        self._scanned_detector = scanned_detector

    def extract(self, pdf_path: Path) -> ExtractedDocument:
        raw = self._markitdown.convert(pdf_path)
        is_scanned = self._scanned_detector.is_scanned(raw.markdown, raw.pages)
        normalized_markdown = self._normalizer.normalize(raw.markdown, raw.pages)

        bibliography = self._extract_bibliography(pdf_path, normalized_markdown)

        return ExtractedDocument(
            markdown=normalized_markdown,
            pages=raw.pages,
            bibliography=bibliography,
            is_scanned=is_scanned,
        )

    def _extract_bibliography(self, pdf_path: Path, markdown: str) -> BibliographicMetadata:
        bibliography = BibliographicMetadata()

        if self._grobid is not None:
            try:
                bibliography = self._grobid.extract_header(pdf_path)
            except GrobidUnavailableError:
                logger.warning("GROBID unavailable for %s, falling back to null metadata", pdf_path)

        if bibliography.institution is None:
            fallback_institution = guess_institution(markdown)
            if fallback_institution is not None:
                bibliography = replace_institution(bibliography, fallback_institution)

        return bibliography


def replace_institution(
    bibliography: BibliographicMetadata, institution: str
) -> BibliographicMetadata:
    """Returns a copy of bibliography with `institution` filled in (frozen VO)."""
    return bibliography.model_copy(update={"institution": institution})
