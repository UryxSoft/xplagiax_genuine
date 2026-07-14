"""Read-only index view that follows the manifest (ADR-010 hot reload).

Web replicas hold one of these instead of a raw index: before serving a
search it compares the manifest version with the loaded one and reloads
the new snapshot when the indexer worker has published a version. Reload
is a fresh factory call (mmap open), the old object is dropped afterwards
-- readers never observe a half-updated index.

Mutations raise: writes belong exclusively to the VersionedIndexWriter in
the worker process (single-writer topology). The API layer must route
index/delete through jobs when this view is in use (worker_mode).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.domain.value_objects.search_hit import SearchHit
from app.infrastructure.persistence.index_manifest import IndexManifest


class ReadOnlyIndexError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "this replica holds a read-only index view; writes go through the indexer worker"
        )


class HotReloadingVectorIndex:
    def __init__(self, index_factory: Callable[[Path | None], object], data_dir: Path) -> None:
        self._factory = index_factory
        self._manifest = IndexManifest(data_dir)
        self._loaded_version = -1
        self._index: object | None = None
        self._maybe_reload()

    @property
    def dimension(self) -> int:
        self._maybe_reload()
        return self._index.dimension  # type: ignore[union-attr]

    @property
    def version(self) -> int:
        self._maybe_reload()
        return self._loaded_version

    def search(
        self, query: EmbeddingVector, k: int, allowlist: set[int] | None = None
    ) -> list[SearchHit]:
        self._maybe_reload()
        return self._index.search(query, k, allowlist)  # type: ignore[union-attr]

    def add(self, chunk_ids: list[int], vectors: list[EmbeddingVector]) -> None:
        raise ReadOnlyIndexError()

    def remove(self, chunk_id: int) -> None:
        raise ReadOnlyIndexError()

    def snapshot(self) -> None:
        raise ReadOnlyIndexError()

    def _maybe_reload(self) -> None:
        state = self._manifest.read()
        current_version = state.version if state else 0
        if self._index is None or current_version != self._loaded_version:
            self._index = self._factory(self._manifest.index_path())
            self._loaded_version = current_version
