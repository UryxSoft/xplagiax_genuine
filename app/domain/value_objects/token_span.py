"""Position of a segment within a document, expressed in token offsets."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class TokenSpan(BaseModel):
    """Half-open token range [start, end) plus optional page number.

    `page` is None when the extraction stage does not preserve page
    boundaries in the normalized Markdown (honest gap, not fabricated).
    """

    model_config = {"frozen": True}

    start: int
    end: int
    page: int | None = None

    @model_validator(mode="after")
    def _check_order(self) -> "TokenSpan":
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"invalid span: start={self.start}, end={self.end}")
        return self
