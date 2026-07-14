"""Write-ahead log for index mutations (ADR-010, NFR-07).

JSONL, one entry per mutation, fsync'd before the mutation is applied to
the in-memory index: a crash between append and apply replays the entry on
restart; a crash before append means the operation was never acknowledged.
Entries carry the actual vectors (not the source text) so replay never
needs the embedding model.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class WriteAheadLog:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, entry: dict[str, Any]) -> None:
        line = json.dumps(entry, separators=(",", ":"))
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    # torn write from a crash mid-append: everything before
                    # this line was fsync'd and valid; the torn tail was
                    # never acknowledged, so it is safe to stop here.
                    break
        return entries

    def truncate(self) -> None:
        if self._path.exists():
            self._path.unlink()
