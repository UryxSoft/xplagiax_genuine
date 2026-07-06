"""Port (hexagonal architecture) for PDF text/metadata extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.domain.value_objects.extracted_document import ExtractedDocument


class DocumentParser(Protocol):
    """Extracts normalized Markdown and bibliographic metadata from a PDF.

    Implementations must never raise on missing metadata: absent fields
    are represented as None inside BibliographicMetadata (RF-08).
    """

    def extract(self, pdf_path: Path) -> ExtractedDocument:
        ...
