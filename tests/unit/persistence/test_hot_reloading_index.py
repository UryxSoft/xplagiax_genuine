from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.infrastructure.persistence.hot_reloading_index import (
    HotReloadingVectorIndex,
    ReadOnlyIndexError,
)
from app.infrastructure.persistence.index_manifest import IndexManifest
from tests.integration.inmemory import InMemoryVectorIndex


class _CountingFactory:
    def __init__(self) -> None:
        self.loads = 0

    def __call__(self, path: Path | None) -> InMemoryVectorIndex:
        self.loads += 1
        if path is not None and path.exists():
            return InMemoryVectorIndex.from_file(path, dimension=2)
        return InMemoryVectorIndex(dimension=2)


def _publish(tmp_path: Path, version: int, chunk_ids: list[int]) -> None:
    index = InMemoryVectorIndex(dimension=2)
    index.add(chunk_ids, [EmbeddingVector(values=(1.0, 0.0)) for _ in chunk_ids])
    filename = f"index.v{version}"
    index.write_to(tmp_path / filename)
    IndexManifest(tmp_path).commit(version, filename)


def test_loads_current_version_on_construction(tmp_path: Path) -> None:
    _publish(tmp_path, 1, [1, 2])
    reader = HotReloadingVectorIndex(_CountingFactory(), tmp_path)

    hits = reader.search(EmbeddingVector(values=(1.0, 0.0)), k=5)
    assert {h.chunk_id for h in hits} == {1, 2}
    assert reader.version == 1


def test_reloads_when_manifest_advances(tmp_path: Path) -> None:
    _publish(tmp_path, 1, [1])
    factory = _CountingFactory()
    reader = HotReloadingVectorIndex(factory, tmp_path)
    loads_before = factory.loads

    _publish(tmp_path, 2, [1, 2, 3])

    hits = reader.search(EmbeddingVector(values=(1.0, 0.0)), k=5)
    assert {h.chunk_id for h in hits} == {1, 2, 3}
    assert factory.loads == loads_before + 1
    assert reader.version == 2


def test_no_reload_when_version_unchanged(tmp_path: Path) -> None:
    _publish(tmp_path, 1, [1])
    factory = _CountingFactory()
    reader = HotReloadingVectorIndex(factory, tmp_path)
    loads_before = factory.loads

    reader.search(EmbeddingVector(values=(1.0, 0.0)), k=5)
    reader.search(EmbeddingVector(values=(1.0, 0.0)), k=5)

    assert factory.loads == loads_before


def test_writes_are_rejected(tmp_path: Path) -> None:
    reader = HotReloadingVectorIndex(_CountingFactory(), tmp_path)

    with pytest.raises(ReadOnlyIndexError):
        reader.add([1], [EmbeddingVector(values=(1.0, 0.0))])
    with pytest.raises(ReadOnlyIndexError):
        reader.remove(1)
    with pytest.raises(ReadOnlyIndexError):
        reader.snapshot()
