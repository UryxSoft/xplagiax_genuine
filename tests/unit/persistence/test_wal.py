from pathlib import Path

from app.infrastructure.persistence.wal import WriteAheadLog


def test_append_and_read_round_trip(tmp_path: Path) -> None:
    wal = WriteAheadLog(tmp_path / "index.wal")
    wal.append({"op": "add", "ids": [1, 2]})
    wal.append({"op": "remove", "id": 1})

    assert wal.read_all() == [{"op": "add", "ids": [1, 2]}, {"op": "remove", "id": 1}]


def test_read_missing_file_is_empty(tmp_path: Path) -> None:
    assert WriteAheadLog(tmp_path / "nope.wal").read_all() == []


def test_truncate_clears_log(tmp_path: Path) -> None:
    wal = WriteAheadLog(tmp_path / "index.wal")
    wal.append({"op": "remove", "id": 7})
    wal.truncate()
    assert wal.read_all() == []
    wal.truncate()  # idempotent on missing file


def test_torn_tail_from_crash_is_ignored(tmp_path: Path) -> None:
    wal = WriteAheadLog(tmp_path / "index.wal")
    wal.append({"op": "remove", "id": 1})
    with wal.path.open("a", encoding="utf-8") as handle:
        handle.write('{"op": "add", "ids": [2')  # crash mid-write

    assert wal.read_all() == [{"op": "remove", "id": 1}]
