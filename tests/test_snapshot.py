import json
from unittest.mock import patch

from ghsnitch.snapshot import compute_scope


def _make_snapshot_file(tmp_path, data, filename="snapshot.json"):
    f = tmp_path / filename
    f.write_text(json.dumps(data))
    return f


def test_compute_scope_basic():
    scope1 = compute_scope(["alice", "bob"], "https://github.com")
    scope2 = compute_scope(["bob", "alice"], "https://github.com")
    assert scope1 == scope2
    assert len(scope1) == 12


def test_compute_scope_different_url():
    scope1 = compute_scope(["alice"], "https://github.com")
    scope2 = compute_scope(["alice"], "https://github.example.com")
    assert scope1 != scope2


# --- load_snapshot ---


def test_load_snapshot_returns_none_when_missing(tmp_path):
    with patch("ghsnitch.snapshot._LEGACY_SNAPSHOT_FILE", tmp_path / "snapshot.json"):
        from ghsnitch.snapshot import load_snapshot

        assert load_snapshot() is None


def test_load_snapshot_returns_data(tmp_path):
    payload = {
        "timestamp": "2026-04-05T12:00:00+00:00",
        "contributions": {"alice": {"2026": 50}},
    }
    snap = _make_snapshot_file(tmp_path, payload)
    with patch("ghsnitch.snapshot._LEGACY_SNAPSHOT_FILE", snap):
        from ghsnitch.snapshot import load_snapshot

        result = load_snapshot()
    assert result["contributions"]["alice"]["2026"] == 50


def test_load_snapshot_scoped(tmp_path):
    payload = {
        "timestamp": "2026-04-05T12:00:00+00:00",
        "contributions": {"alice": {"2026": 50}},
    }
    _make_snapshot_file(tmp_path, payload, "snapshot-abc.json")
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import load_snapshot

        result = load_snapshot(scope="abc")
    assert result["contributions"]["alice"]["2026"] == 50


def test_load_snapshot_context_id(tmp_path):
    payload = {
        "timestamp": "2026-04-05T12:00:00+00:00",
        "contributions": {"alice": {"2026": 50}},
    }
    _make_snapshot_file(tmp_path, payload, "snapshot-team-alpha.json")
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import load_snapshot

        result = load_snapshot(context_id="team-alpha")
    assert result["contributions"]["alice"]["2026"] == 50


# --- save_snapshot ---


def test_save_snapshot_writes_file(tmp_path):
    snap = tmp_path / "snapshot.json"
    with patch("ghsnitch.snapshot._LEGACY_SNAPSHOT_FILE", snap):
        with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
            from ghsnitch.snapshot import save_snapshot

            save_snapshot({"alice": {"2026": 100}})
    data = json.loads(snap.read_text())
    assert data["contributions"]["alice"]["2026"] == 100
    assert "timestamp" in data


def test_save_snapshot_scoped(tmp_path):
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import save_snapshot

        save_snapshot({"bob": {"2026": 75}}, scope="xyz")
    snap = tmp_path / "snapshot-xyz.json"
    assert snap.exists()
    data = json.loads(snap.read_text())
    assert data["contributions"]["bob"]["2026"] == 75


def test_save_snapshot_context_id(tmp_path):
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import save_snapshot

        save_snapshot({"bob": {"2026": 75}}, context_id="team-beta")
    snap = tmp_path / "snapshot-team-beta.json"
    assert snap.exists()


# --- clear_all_snapshots ---


def test_clear_all_snapshots(tmp_path):
    _make_snapshot_file(tmp_path, {}, "snapshot.json")
    _make_snapshot_file(tmp_path, {}, "snapshot-abc.json")
    _make_snapshot_file(tmp_path, {}, "snapshot-team-alpha.json")
    _make_snapshot_file(tmp_path, {}, "not-a-snapshot.txt")

    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        with patch(
            "ghsnitch.snapshot._LEGACY_SNAPSHOT_FILE", tmp_path / "snapshot.json"
        ):
            from ghsnitch.snapshot import clear_all_snapshots

            assert clear_all_snapshots() is True

    assert not (tmp_path / "snapshot.json").exists()
    assert not (tmp_path / "snapshot-abc.json").exists()
    assert not (tmp_path / "snapshot-team-alpha.json").exists()
    assert (tmp_path / "not-a-snapshot.txt").exists()
