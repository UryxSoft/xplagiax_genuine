import pytest

from app.application.ranking.plagiarism_scorer import SIMPLE_WEIGHTS, SOTA_WEIGHTS, PlagiarismScorer
from app.domain.value_objects.rerank_signals import RerankSignals


def test_all_signals_present_full_similarity_yields_100_percent() -> None:
    scorer = PlagiarismScorer(SOTA_WEIGHTS)
    signals = RerankSignals(embedding=1.0, topic=1.0, language=1.0, minhash=1.0, simhash=1.0, entity=1.0, exact=1.0)

    result = scorer.score(signals)

    assert result.percent == pytest.approx(100.0)
    assert result.verdict == "Plagio casi identico"


def test_all_signals_zero_yields_zero_percent() -> None:
    scorer = PlagiarismScorer(SOTA_WEIGHTS)
    signals = RerankSignals(embedding=0.0, topic=0.0, language=0.0, minhash=0.0, simhash=0.0, entity=0.0, exact=0.0)

    result = scorer.score(signals)

    assert result.percent == pytest.approx(0.0)
    assert result.verdict == "Baja similitud"


def test_missing_signal_renormalizes_remaining_weights() -> None:
    scorer = PlagiarismScorer(SOTA_WEIGHTS)
    # entity is None (no institution match available) but everything else is perfect
    signals = RerankSignals(embedding=1.0, topic=1.0, language=1.0, minhash=1.0, simhash=1.0, entity=None, exact=1.0)

    result = scorer.score(signals)

    assert result.percent == pytest.approx(100.0)  # renormalized weights still sum to full score
    assert "entity" not in result.breakdown


def test_no_signals_present_yields_zero_and_empty_breakdown() -> None:
    scorer = PlagiarismScorer(SOTA_WEIGHTS)
    signals = RerankSignals()  # all None

    result = scorer.score(signals)

    assert result.percent == 0.0
    assert result.breakdown == {}


def test_verdict_thresholds() -> None:
    scorer = PlagiarismScorer({"embedding": 1.0})
    assert scorer.score(RerankSignals(embedding=0.96)).verdict == "Plagio casi identico"
    assert scorer.score(RerankSignals(embedding=0.90)).verdict == "Alta probabilidad"
    assert scorer.score(RerankSignals(embedding=0.75)).verdict == "Coincidencia importante"
    assert scorer.score(RerankSignals(embedding=0.55)).verdict == "Similitud tematica"
    assert scorer.score(RerankSignals(embedding=0.10)).verdict == "Baja similitud"


def test_simple_profile_uses_four_terms_only() -> None:
    scorer = PlagiarismScorer(SIMPLE_WEIGHTS)
    signals = RerankSignals(embedding=1.0, topic=1.0, language=1.0, entity=1.0, minhash=1.0, simhash=1.0, exact=1.0)

    result = scorer.score(signals)

    assert set(result.breakdown.keys()) == {"embedding", "topic", "language", "entity"}
    assert result.percent == pytest.approx(100.0)


def test_rejects_weights_not_summing_to_one() -> None:
    with pytest.raises(ValueError):
        PlagiarismScorer({"embedding": 0.5, "topic": 0.3})
