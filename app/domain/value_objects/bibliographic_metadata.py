"""Bibliographic metadata extracted from an academic document."""

from __future__ import annotations

from pydantic import BaseModel


class BibliographicMetadata(BaseModel):
    """Author/institution metadata. All fields are optional (null-safe).

    Missing extraction must yield None, never a fabricated placeholder
    (RF-08).
    """

    model_config = {"frozen": True}

    title: str | None = None
    authors: tuple[str, ...] = ()
    institution: str | None = None
    country: str | None = None
    faculty: str | None = None
    career: str | None = None
    year: int | None = None
