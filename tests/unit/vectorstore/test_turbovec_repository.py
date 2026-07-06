import sys
import types

import numpy as np
import pytest

from app.domain.value_objects.embedding_vector import EmbeddingVector


class _FakeIdMapIndex:
    """Brute-force in-memory stand-in for turbovec.IdMapIndex.

    Honors the real library's allowlist semantics: allowlist=None means
    unrestricted, an explicit (possibly empty) array restricts candidates
    and the result length is min(k, len(allowlist)).
    """

    loaded_from: list[str] = []
    written_to: list[str] = []

    def __init__(self, dim: int, bit_width: int) -> None:
        self.dim = dim
        self.bit_width = bit_width
        self._vectors: dict[int, np.ndarray] = {}

    @classmethod
    def load(cls, path: str) -> "_FakeIdMapIndex":
        cls.loaded_from.append(path)
        instance = cls(dim=4, bit_width=4)
        return instance

    def add_with_ids(self, vectors: np.ndarray, ids: np.ndarray) -> None:
        for vec, id_ in zip(vectors, ids):
            self._vectors[int(id_)] = vec

    def search(self, query: np.ndarray, k: int, allowlist: np.ndarray | None = None):
        if allowlist is not None:
            candidate_ids = [i for i in self._vectors if i in set(allowlist.tolist())]
        else:
            candidate_ids = list(self._vectors.keys())

        scored = [(float(np.dot(query, self._vectors[i])), i) for i in candidate_ids]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = scored[:k]
        scores = np.array([s for s, _ in top], dtype=np.float32)
        ids = np.array([i for _, i in top], dtype=np.uint64)
        return scores, ids

    def remove(self, chunk_id: int) -> None:
        self._vectors.pop(chunk_id, None)

    def write(self, path: str) -> None:
        _FakeIdMapIndex.written_to.append(path)


@pytest.fixture(autouse=True)
def _stub_turbovec(monkeypatch):
    fake_module = types.ModuleType("turbovec")
    fake_module.IdMapIndex = _FakeIdMapIndex
    monkeypatch.setitem(sys.modules, "turbovec", fake_module)
    _FakeIdMapIndex.loaded_from = []
    _FakeIdMapIndex.written_to = []
    yield


def _vec(*values: float) -> EmbeddingVector:
    return EmbeddingVector(values=values)


def test_add_and_search_returns_closest_match_first() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

    repo = TurboVecRepository(dimension=4)
    repo.add(
        [1, 2],
        [_vec(1.0, 0.0, 0.0, 0.0), _vec(0.0, 1.0, 0.0, 0.0)],
    )

    hits = repo.search(_vec(0.9, 0.1, 0.0, 0.0), k=2)

    assert [h.chunk_id for h in hits] == [1, 2]
    assert hits[0].score > hits[1].score


def test_search_respects_none_allowlist_unrestricted() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

    repo = TurboVecRepository(dimension=4)
    repo.add([1, 2, 3], [_vec(1, 0, 0, 0), _vec(0, 1, 0, 0), _vec(0, 0, 1, 0)])

    hits = repo.search(_vec(1, 1, 1, 0), k=10, allowlist=None)

    assert {h.chunk_id for h in hits} == {1, 2, 3}


def test_search_with_empty_allowlist_returns_no_results() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

    repo = TurboVecRepository(dimension=4)
    repo.add([1, 2], [_vec(1, 0, 0, 0), _vec(0, 1, 0, 0)])

    hits = repo.search(_vec(1, 1, 0, 0), k=10, allowlist=set())

    assert hits == []


def test_search_with_specific_allowlist_restricts_candidates() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

    repo = TurboVecRepository(dimension=4)
    repo.add([1, 2, 3], [_vec(1, 0, 0, 0), _vec(0, 1, 0, 0), _vec(0, 0, 1, 0)])

    hits = repo.search(_vec(1, 1, 1, 0), k=10, allowlist={2, 3})

    assert {h.chunk_id for h in hits} == {2, 3}


def test_remove_excludes_id_from_future_searches() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

    repo = TurboVecRepository(dimension=4)
    repo.add([1, 2], [_vec(1, 0, 0, 0), _vec(0, 1, 0, 0)])
    repo.remove(1)

    hits = repo.search(_vec(1, 1, 0, 0), k=10)

    assert {h.chunk_id for h in hits} == {2}


def test_add_rejects_dimension_mismatch() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import (
        DimensionMismatchError,
        TurboVecRepository,
    )

    repo = TurboVecRepository(dimension=4)
    with pytest.raises(DimensionMismatchError):
        repo.add([1], [_vec(1, 0, 0)])  # dim 3, expected 4


def test_search_rejects_dimension_mismatch() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import (
        DimensionMismatchError,
        TurboVecRepository,
    )

    repo = TurboVecRepository(dimension=4)
    with pytest.raises(DimensionMismatchError):
        repo.search(_vec(1, 0, 0), k=5)


def test_search_rejects_non_positive_k() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

    repo = TurboVecRepository(dimension=4)
    with pytest.raises(ValueError):
        repo.search(_vec(1, 0, 0, 0), k=0)


def test_add_rejects_mismatched_ids_and_vectors_length() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

    repo = TurboVecRepository(dimension=4)
    with pytest.raises(ValueError):
        repo.add([1, 2], [_vec(1, 0, 0, 0)])


def test_add_with_empty_lists_is_a_noop() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

    repo = TurboVecRepository(dimension=4)
    repo.add([], [])  # must not raise
    assert repo.search(_vec(1, 0, 0, 0), k=5) == []


def test_snapshot_without_index_path_raises() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

    repo = TurboVecRepository(dimension=4)
    with pytest.raises(ValueError):
        repo.snapshot()


def test_snapshot_writes_and_increments_version(tmp_path) -> None:
    from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

    index_path = tmp_path / "index.tvim"
    repo = TurboVecRepository(dimension=4, index_path=index_path)

    assert repo.version == 0
    repo.snapshot()
    assert repo.version == 1
    assert str(index_path) in _FakeIdMapIndex.written_to


def test_existing_index_path_is_loaded_not_recreated(tmp_path) -> None:
    from app.infrastructure.vectorstore.turbovec_repository import TurboVecRepository

    index_path = tmp_path / "index.tvim"
    index_path.write_bytes(b"fake persisted index")

    TurboVecRepository(dimension=4, index_path=index_path)

    assert str(index_path) in _FakeIdMapIndex.loaded_from


def test_default_bit_width_is_four() -> None:
    from app.infrastructure.vectorstore.turbovec_repository import (
        DEFAULT_BIT_WIDTH,
        TurboVecRepository,
    )

    assert DEFAULT_BIT_WIDTH == 4
    repo = TurboVecRepository(dimension=4)
    assert repo._bit_width == 4
