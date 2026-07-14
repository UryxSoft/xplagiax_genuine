from pathlib import Path

from app.infrastructure.persistence.index_manifest import IndexManifest


def test_read_before_any_commit_is_none(tmp_path: Path) -> None:
    manifest = IndexManifest(tmp_path)
    assert manifest.read() is None
    assert manifest.index_path() is None


def test_commit_then_read(tmp_path: Path) -> None:
    manifest = IndexManifest(tmp_path)
    manifest.commit(3, "index.v3")

    state = manifest.read()
    assert state.version == 3
    assert state.index_filename == "index.v3"
    assert manifest.index_path() == tmp_path / "index.v3"


def test_commit_replaces_atomically(tmp_path: Path) -> None:
    manifest = IndexManifest(tmp_path)
    manifest.commit(1, "index.v1")
    manifest.commit(2, "index.v2")

    assert manifest.read().version == 2
    assert not (tmp_path / "manifest.tmp").exists()


def test_two_instances_share_state(tmp_path: Path) -> None:
    IndexManifest(tmp_path).commit(5, "index.v5")
    assert IndexManifest(tmp_path).read().version == 5
