"""Dense embedding vector produced by an EmbeddingModel."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class EmbeddingVector(BaseModel):
    """Immutable dense vector. `values` is a tuple for hashability/equality."""

    model_config = {"frozen": True}

    values: tuple[float, ...]

    @model_validator(mode="after")
    def _non_empty(self) -> "EmbeddingVector":
        if not self.values:
            raise ValueError("embedding vector must not be empty")
        return self

    @property
    def dimension(self) -> int:
        return len(self.values)
