"""Final composite plagiarism score and verdict (ADR sect 12)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlagiarismScore(BaseModel):
    model_config = {"frozen": True}

    percent: float = Field(ge=0.0, le=100.0)
    breakdown: dict[str, float]
    verdict: str


def verdict_for(percent: float) -> str:
    if percent >= 95:
        return "Plagio casi identico"
    if percent >= 85:
        return "Alta probabilidad"
    if percent >= 70:
        return "Coincidencia importante"
    if percent >= 50:
        return "Similitud tematica"
    return "Baja similitud"
