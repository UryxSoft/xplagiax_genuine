"""VersionedIndexWriter over the JSON-backed InMemoryVectorIndex: WAL-first
writes, threshold checkpoints, crash recovery by snapshot + replay."""

from __future__ import annotations

from pathlib import Path

from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.infrastructure.persistence.index_manifest import IndexManifest
from app.infrastructure.persistence.versioned_index_writer import VersionedIndexWriter
from app.infrastructure.persistence.wal import WriteAheadLog
from tests.integration.inmemory import InMemoryVectorIndex


def _factory(path: Path | None) -> InMemoryVectorIndex:
    if path is not None and path.exists():
        return InMemoryVectorIndex.from_file(path, dimension=2)
    return InMemoryVectorIndex(dimension=2)


def _vec(x: float, y: float) -> EmbeddingVector:
    return EmbeddingVector(values=(x, y))


def test_add_is_wal_logged_before_checkpoint(tmp_path: Path) -> None:
    writer = VersionedIndexWriter(_factory, tmp_path, checkpoint_every_ops=100)
    writer.add([1], [_vec(1.0, 0.0)])

    wal = WriteAheadLog(tmp_path / "index.wal")
    assert wal.read_all() == [{"op": "add", "ids": [1], "vectors": [[1.0, 0.0]]}]
    assert IndexManifest(tmp_path).read() is None  # not yet checkpointed


def test_checkpoint_at_threshold_bumps_manifest_and_truncates_wal(tmp_path: Path) -> None:
    writer = VersionedIndexWriter(_factory, tmp_path, checkpoint_every_ops=2)
    writer.add([1], [_vec(1.0, 0.0)])
    writer.add([2], [_vec(0.0, 1.0)])  # second op: checkpoint fires

    state = IndexManifest(tmp_path).read()
    assert state.version == 1
    assert (tmp_path / state.index_filename).exists()
    assert WriteAheadLog(tmp_path / "index.wal").read_all() == []
    assert writer.version == 1


def test_crash_recovery_replays_wal_over_snapshot(tmp_path: Path) -> None:
    writer = VersionedIndexWriter(_factory, tmp_path, checkpoint_every_ops=2)
    writer.add([1], [_vec(1.0, 0.0)])
    writer.add([2], [_vec(0.0, 1.0)])  # checkpointed snapshot v1
    writer.add([3], [_vec(1.0, 1.0)])  # only in WAL
    # "crash": writer dropped without further checkpoint

    recovered = VersionedIndexWriter(_factory, tmp_path, checkpoint_every_ops=100)

    hits = recovered.search(_vec(1.0, 1.0), k=3)
    assert {h.chunk_id for h in hits} == {1, 2, 3}


def test_recovery_replays_removes_too(tmp_path: Path) -> None:
    writer = VersionedIndexWriter(_factory, tmp_path, checkpoint_every_ops=2)
    writer.add([1], [_vec(1.0, 0.0)])
    writer.add([2], [_vec(0.0, 1.0)])  # snapshot v1 contains 1 and 2
    writer.remove(1)  # only in WAL

    recovered = VersionedIndexWriter(_factory, tmp_path, checkpoint_every_ops=100)

    hits = recovered.search(_vec(1.0, 0.0), k=3)
    assert {h.chunk_id for h in hits} == {2}


def test_snapshot_alias_checkpoints_pending_ops(tmp_path: Path) -> None:
    writer = VersionedIndexWriter(_factory, tmp_path, checkpoint_every_ops=100)
    writer.add([1], [_vec(1.0, 0.0)])
    writer.snapshot()

    assert IndexManifest(tmp_path).read().version == 1
    assert WriteAheadLog(tmp_path / "index.wal").read_all() == []


def test_checkpoint_without_pending_ops_is_noop(tmp_path: Path) -> None:
    writer = VersionedIndexWriter(_factory, tmp_path, checkpoint_every_ops=100)
    writer.checkpoint()
    assert IndexManifest(tmp_path).read() is None


def test_old_versions_are_pruned_keeping_previous(tmp_path: Path) -> None:
    writer = VersionedIndexWriter(_factory, tmp_path, checkpoint_every_ops=1)
    for i in range(1, 5):  # 4 checkpoints -> versions 1..4
        writer.add([i], [_vec(float(i), 0.0)])

    files = {p.name for p in tmp_path.glob("index.v*")}
    assert files == {"index.v3", "index.v4"}  # current + previous survive
