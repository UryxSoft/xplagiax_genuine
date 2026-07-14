"""Manifest naming the current committed index version (ADR-010).

A tiny JSON file updated by atomic rename: readers either see the previous
complete version or the new complete version, never a half-written one.
The snapshot file itself is written BEFORE the manifest flips, so a crash
between the two leaves the old version current -- and the WAL still holds
the not-yet-checkpointed operations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel

MANIFEST_FILENAME = "manifest.json"


class ManifestState(BaseModel):
    model_config = {"frozen": True}

    version: int
    index_filename: str


class IndexManifest:
    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / MANIFEST_FILENAME

    def read(self) -> ManifestState | None:
        if not self._path.exists():
            return None
        return ManifestState.model_validate(json.loads(self._path.read_text(encoding="utf-8")))

    def commit(self, version: int, index_filename: str) -> None:
        state = ManifestState(version=version, index_filename=index_filename)
        tmp_path = self._path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(state.model_dump_json())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, self._path)

    def index_path(self) -> Path | None:
        state = self.read()
        return self._dir / state.index_filename if state else None
