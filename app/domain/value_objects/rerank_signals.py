"""Raw 0..1 component scores feeding the composite plagiarism score (ADR sect 12).

Each field is None when its signal could not be computed (e.g. no
institution detected in either the query or the candidate document) --
PlagiarismScorer re-normalizes weights over whatever is present, per
docs/DOMAIN_MODEL.md sect 11 ScoreNormalizationPolicy.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class RerankSignals(BaseModel):
    model_config = {"frozen": True}

    embedding: float | None = None
    topic: float | None = None
    language: float | None = None
    minhash: float | None = None
    simhash: float | None = None
    entity: float | None = None
    exact: float | None = None

    @field_validator("embedding", "topic", "language", "minhash", "simhash", "entity", "exact")
    @classmethod
    def _in_unit_range(cls, value: float | None) -> float | None:
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"signal must be in [0, 1], got {value}")
        return value
