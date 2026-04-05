import json
from pathlib import Path
from unittest.mock import patch


def _make_snapshot_file(tmp_path, data):
    f = tmp_path / "snapshot.json"
    f.write_text(json.dumps(data))
    return f


# --- load_snapshot ---


def test_load_snapshot_returns_none_when_missing(tmp_path):
    with patch("ghsnitch.snapshot._SNAPSHOT_FILE", tmp_path / "snapshot.json"):
        from ghsnitch.snapshot import load_snapshot

        assert load_snapshot() is None


def test_load_snapshot_returns_data(tmp_path):
    payload = {
        "timestamp": "2026-04-05T12:00:00+00:00",
        "contributions": {"alice": {"2026": 50}},
    }
    snap = _make_snapshot_file(tmp_path, payload)
    with patch("ghsnitch.snapshot._SNAPSHOT_FILE", snap):
        from ghsnitch.snapshot import load_snapshot

        result = load_snapshot()
    assert result["contributions"]["alice"]["2026"] == 50


def test_load_snapshot_returns_none_on_corrupt_json(tmp_path):
    snap = tmp_path / "snapshot.json"
    snap.write_text("not json{{")
    with patch("ghsnitch.snapshot._SNAPSHOT_FILE", snap):
        from ghsnitch.snapshot import load_snapshot

        assert load_snapshot() is None


# --- save_snapshot ---


def test_save_snapshot_writes_file(tmp_path):
    snap = tmp_path / "snapshot.json"
    with patch("ghsnitch.snapshot._SNAPSHOT_FILE", snap):
        with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
            from ghsnitch.snapshot import save_snapshot

            save_snapshot({"alice": {"2026": 100}})
    data = json.loads(snap.read_text())
    assert data["contributions"]["alice"]["2026"] == 100
    assert "timestamp" in data


def test_save_snapshot_creates_parent_dirs(tmp_path):
    snap = tmp_path / "nested" / "dir" / "snapshot.json"
    with patch("ghsnitch.snapshot._SNAPSHOT_FILE", snap):
        with patch("ghsnitch.snapshot.CACHE_DIR", snap.parent):
            from ghsnitch.snapshot import save_snapshot

            save_snapshot({"bob": {"2026": 5}})
    assert snap.exists()


def test_save_snapshot_silently_ignores_os_error(tmp_path):
    snap = tmp_path / "snapshot.json"
    snap.mkdir()  # make it a directory so write fails
    with patch("ghsnitch.snapshot._SNAPSHOT_FILE", snap):
        with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
            from ghsnitch.snapshot import save_snapshot

            save_snapshot({"alice": {"2026": 10}})  # should not raise


# --- clear_snapshot ---


def test_clear_snapshot_deletes_file(tmp_path):
    snap = _make_snapshot_file(tmp_path, {"contributions": {}})
    with patch("ghsnitch.snapshot._SNAPSHOT_FILE", snap):
        from ghsnitch.snapshot import clear_snapshot

        result = clear_snapshot()
    assert result is True
    assert not snap.exists()


def test_clear_snapshot_returns_true_when_no_file(tmp_path):
    with patch("ghsnitch.snapshot._SNAPSHOT_FILE", tmp_path / "snapshot.json"):
        from ghsnitch.snapshot import clear_snapshot

        assert clear_snapshot() is True


def test_clear_snapshot_returns_false_on_os_error(tmp_path):
    snap = tmp_path / "snapshot.json"

    def _bad_unlink(*_args, **_kwargs):
        raise OSError("permission denied")

    with patch("ghsnitch.snapshot._SNAPSHOT_FILE", snap):
        with patch.object(Path, "unlink", _bad_unlink):
            from ghsnitch.snapshot import clear_snapshot

            assert clear_snapshot() is False
