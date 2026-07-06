"""Value objects describing the origin file of a Document."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

ALLOWED_MIME_TYPES = frozenset({"application/pdf"})
MAX_PDF_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB


class PdfSource(BaseModel):
    """Immutable descriptor of an ingested PDF file.

    Invariant: mime must be application/pdf and size must not exceed
    MAX_PDF_SIZE_BYTES (NFR-10, path traversal / MIME guard is enforced
    by the caller before constructing this value object).
    """

    model_config = {"frozen": True}

    filename: str
    path: str
    pages: int = Field(ge=0)
    mime: str
    size_bytes: int = Field(ge=0)

    @field_validator("mime")
    @classmethod
    def _validate_mime(cls, value: str) -> str:
        if value not in ALLOWED_MIME_TYPES:
            raise ValueError(f"unsupported mime type: {value}")
        return value

    @field_validator("size_bytes")
    @classmethod
    def _validate_size(cls, value: int) -> int:
        if value > MAX_PDF_SIZE_BYTES:
            raise ValueError(f"file exceeds max size of {MAX_PDF_SIZE_BYTES} bytes")
        return value
