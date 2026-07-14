import pytest

from app.application.indexing.chunk_id_factory import chunk_id_for


def test_deterministic_for_same_inputs() -> None:
    assert chunk_id_for("doc-1", 0) == chunk_id_for("doc-1", 0)


def test_differs_across_orders_and_documents() -> None:
    ids = {
        chunk_id_for("doc-1", 0),
        chunk_id_for("doc-1", 1),
        chunk_id_for("doc-2", 0),
        chunk_id_for("doc-2", 1),
    }
    assert len(ids) == 4


def test_fits_in_signed_bigint() -> None:
    for order in range(100):
        chunk_id = chunk_id_for("some-uuid-value", order)
        assert 0 <= chunk_id < 2**63


def test_negative_order_rejected() -> None:
    with pytest.raises(ValueError):
        chunk_id_for("doc-1", -1)
