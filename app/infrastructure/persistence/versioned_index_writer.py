"""Single-writer wrapper adding WAL + versioned snapshots to a vector index
(ADR-010: immutable versioned index, WAL, checkpoints).

Topology contract: exactly ONE process holds a VersionedIndexWriter (the
indexer worker, Fase 3); web replicas hold read-only
HotReloadingVectorIndex instances over the same data directory.

Recovery on construction: load the snapshot named by the manifest (if
any), then replay the WAL -- operations acknowledged after the last
checkpoint are re-applied, so nothing acknowledged is ever lost (NFR-07).

checkpoint_every_ops bounds the WAL replay cost after a crash; each
checkpoint writes a NEW index file (index.v{N}) and flips the manifest
atomically, leaving the previous version intact for in-flight readers
(copy-on-write versioning, lock-free reads).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.domain.value_objects.search_hit import SearchHit
from app.infrastructure.persistence.index_manifest import IndexManifest
from app.infrastructure.persistence.wal import WriteAheadLog

WAL_FILENAME = "index.wal"
KEEP_PREVIOUS_VERSIONS = 1


class WritableVectorIndex(Protocol):
    """The inner index: VectorIndexRepository plus write_to(path)."""

    @property
    def dimension(self) -> int: ...

    def add(self, chunk_ids: list[int], vectors: list[EmbeddingVector]) -> None: ...

    def search(
        self, query: EmbeddingVector, k: int, allowlist: set[int] | None = None
    ) -> list[SearchHit]: ...

    def remove(self, chunk_id: int) -> None: ...

    def write_to(self, path: Path) -> None: ...


IndexFactory = Callable[[Path | None], WritableVectorIndex]


class VersionedIndexWriter:
    def __init__(
        self,
        index_factory: IndexFactory,
        data_dir: Path,
        checkpoint_every_ops: int = 50,
    ) -> None:
        if checkpoint_every_ops <= 0:
            raise ValueError("checkpoint_every_ops must be positive")
        self._factory = index_factory
        self._dir = data_dir
        self._manifest = IndexManifest(data_dir)
        self._wal = WriteAheadLog(data_dir / WAL_FILENAME)
        self._checkpoint_every = checkpoint_every_ops
        self._ops_since_checkpoint = 0

        state = self._manifest.read()
        self._version = state.version if state else 0
        self._index = self._factory(self._manifest.index_path())
        self._replay_wal()

    # -- VectorIndexRepository surface -----------------------------------

    @property
    def dimension(self) -> int:
        return self._index.dimension

    @property
    def version(self) -> int:
        return self._version

    def add(self, chunk_ids: list[int], vectors: list[EmbeddingVector]) -> None:
        self._wal.append(
            {"op": "add", "ids": chunk_ids, "vectors": [list(v.values) for v in vectors]}
        )
        self._index.add(chunk_ids, vectors)
        self._after_op()

    def remove(self, chunk_id: int) -> None:
        self._wal.append({"op": "remove", "id": chunk_id})
        self._index.remove(chunk_id)
        self._after_op()

    def search(
        self, query: EmbeddingVector, k: int, allowlist: set[int] | None = None
    ) -> list[SearchHit]:
        return self._index.search(query, k, allowlist)

    def snapshot(self) -> None:
        self.checkpoint()

    # -- checkpointing ----------------------------------------------------

    def checkpoint(self) -> None:
        if self._ops_since_checkpoint == 0:
            return
        new_version = self._version + 1
        filename = f"index.v{new_version}"
        self._index.write_to(self._dir / filename)
        self._manifest.commit(new_version, filename)
        self._wal.truncate()
        self._version = new_version
        self._ops_since_checkpoint = 0
        self._prune_old_versions()

    def _after_op(self) -> None:
        self._ops_since_checkpoint += 1
        if self._ops_since_checkpoint >= self._checkpoint_every:
            self.checkpoint()

    def _replay_wal(self) -> None:
        entries = self._wal.read_all()
        for entry in entries:
            if entry["op"] == "add":
                vectors = [EmbeddingVector(values=tuple(v)) for v in entry["vectors"]]
                self._index.add(entry["ids"], vectors)
            elif entry["op"] == "remove":
                self._index.remove(entry["id"])
        # replayed ops are un-checkpointed by definition
        self._ops_since_checkpoint = len(entries)

    def _prune_old_versions(self) -> None:
        for path in self._dir.glob("index.v*"):
            try:
                file_version = int(path.name.removeprefix("index.v"))
            except ValueError:
                continue
            if file_version < self._version - KEEP_PREVIOUS_VERSIONS:
                path.unlink(missing_ok=True)
