"""Composite plagiarism scoring (ADR sect 12).

Two weight profiles: `sota` (default, 7 terms) is the hybrid score this
project targets; `simple` (4 terms) mirrors the coarser formula from the
original spec and is kept as a configurable alternative, not a fallback.
Weights are re-normalized over whatever signals are actually present
(docs/DOMAIN_MODEL.md sect 11 ScoreNormalizationPolicy) so a missing
signal (e.g. no entity match available) never silently caps the maximum
achievable score.
"""

from __future__ import annotations

from app.domain.value_objects.plagiarism_score import PlagiarismScore, verdict_for
from app.domain.value_objects.rerank_signals import RerankSignals

SOTA_WEIGHTS: dict[str, float] = {
    "embedding": 0.35,
    "topic": 0.20,
    "language": 0.15,
    "minhash": 0.10,
    "simhash": 0.10,
    "entity": 0.05,
    "exact": 0.05,
}

SIMPLE_WEIGHTS: dict[str, float] = {
    "embedding": 0.65,
    "topic": 0.20,
    "language": 0.10,
    "entity": 0.05,
}

_WEIGHT_SUM_TOLERANCE = 1e-6


class PlagiarismScorer:
    def __init__(self, weights: dict[str, float] = SOTA_WEIGHTS) -> None:
        total = sum(weights.values())
        if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"weights must sum to 1.0, got {total}")
        self._weights = weights

    def score(self, signals: RerankSignals) -> PlagiarismScore:
        present = {
            name: value
            for name, value in signals.model_dump().items()
            if value is not None and name in self._weights
        }

        if not present:
            return PlagiarismScore(percent=0.0, breakdown={}, verdict=verdict_for(0.0))

        total_weight = sum(self._weights[name] for name in present)
        normalized_weights = {name: self._weights[name] / total_weight for name in present}

        value = sum(present[name] * normalized_weights[name] for name in present)
        percent = round(value * 100, 4)

        return PlagiarismScore(percent=percent, breakdown=present, verdict=verdict_for(percent))
