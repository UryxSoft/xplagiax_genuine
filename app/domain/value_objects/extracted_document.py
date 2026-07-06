"""Result of the extraction stage (RF-03/RF-04): normalized text plus metadata."""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata


class ExtractedDocument(BaseModel):
    """Normalized Markdown text and bibliographic metadata for one PDF."""

    model_config = {"frozen": True}

    markdown: str
    pages: int
    bibliography: BibliographicMetadata
    is_scanned: bool
