"""Atomic write behaviour: the destination is never seen partially written."""

import json
import os

import pytest

from ghsnitch.atomicio import write_json_atomic, write_text_atomic


def test_write_text_atomic_creates_the_file(tmp_path):
    target = tmp_path / "snapshot.json"

    write_text_atomic(target, "payload")

    assert target.read_text() == "payload"


def test_write_text_atomic_replaces_existing_content(tmp_path):
    target = tmp_path / "snapshot.json"
    target.write_text("old")

    write_text_atomic(target, "new")

    assert target.read_text() == "new"


def test_write_text_atomic_leaves_no_temp_residue(tmp_path):
    target = tmp_path / "snapshot.json"

    write_text_atomic(target, "payload")

    assert [p.name for p in tmp_path.iterdir()] == ["snapshot.json"]


def test_write_text_atomic_writes_its_temp_file_alongside_the_target(
    tmp_path, monkeypatch
):
    """A rename is only atomic within one filesystem, so the temp file must be
    a sibling of the destination rather than in the system temp directory."""
    target = tmp_path / "nested" / "snapshot.json"
    target.parent.mkdir()
    seen = {}

    real_replace = os.replace

    def spy(src, dst):
        seen["parent"] = os.path.dirname(os.fspath(src))
        return real_replace(src, dst)

    monkeypatch.setattr("ghsnitch.atomicio.os.replace", spy)
    write_text_atomic(target, "payload")

    assert seen["parent"] == str(target.parent)


def test_write_text_atomic_leaves_the_old_file_intact_when_the_rename_fails(
    tmp_path, monkeypatch
):
    """The whole point: a failure mid-write must not destroy what was there."""
    target = tmp_path / "snapshot.json"
    target.write_text("original")

    def boom(src, dst):
        raise OSError("rename failed")

    monkeypatch.setattr("ghsnitch.atomicio.os.replace", boom)

    with pytest.raises(OSError):
        write_text_atomic(target, "replacement")

    assert target.read_text() == "original"


def test_write_text_atomic_removes_its_temp_file_when_the_rename_fails(
    tmp_path, monkeypatch
):
    target = tmp_path / "snapshot.json"
    target.write_text("original")

    def boom(src, dst):
        raise OSError("rename failed")

    monkeypatch.setattr("ghsnitch.atomicio.os.replace", boom)

    with pytest.raises(OSError):
        write_text_atomic(target, "replacement")

    assert [p.name for p in tmp_path.iterdir()] == ["snapshot.json"]


def test_write_json_atomic_round_trips(tmp_path):
    target = tmp_path / "cache.json"

    write_json_atomic(target, {"latest_version": "1.2.3"})

    assert json.loads(target.read_text()) == {"latest_version": "1.2.3"}


def test_write_json_atomic_leaves_the_old_file_intact_when_data_cannot_encode(
    tmp_path,
):
    """Serialising before touching the destination is what makes this safe."""
    target = tmp_path / "cache.json"
    target.write_text('{"latest_version": "1.0.0"}')

    with pytest.raises(TypeError):
        write_json_atomic(target, {"when": object()})

    assert json.loads(target.read_text()) == {"latest_version": "1.0.0"}
    assert [p.name for p in tmp_path.iterdir()] == ["cache.json"]
