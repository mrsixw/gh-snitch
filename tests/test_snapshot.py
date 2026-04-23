import json
from pathlib import Path
from unittest.mock import patch

from ghsnitch.snapshot import compute_scope


def _make_snapshot_file(tmp_path, data, scope=None, context_id=None):
    if context_id:
        name = f"snapshot-{context_id}.json"
    elif scope:
        name = f"snapshot-{scope}.json"
    else:
        name = "snapshot.json"
    f = tmp_path / name
    f.write_text(json.dumps(data))
    return f


# --- compute_scope ---


def test_compute_scope_deterministic():
    s1 = compute_scope(["alice", "bob"], "https://github.com")
    s2 = compute_scope(["alice", "bob"], "https://github.com")
    assert s1 == s2


def test_compute_scope_order_independent():
    s1 = compute_scope(["bob", "alice"], "https://github.com")
    s2 = compute_scope(["alice", "bob"], "https://github.com")
    assert s1 == s2


def test_compute_scope_case_insensitive():
    s1 = compute_scope(["Alice", "Bob"], "https://github.com")
    s2 = compute_scope(["alice", "bob"], "https://github.com")
    assert s1 == s2


def test_compute_scope_differs_by_github_url():
    s1 = compute_scope(["alice"], "https://github.com")
    s2 = compute_scope(["alice"], "https://github.example.com")
    assert s1 != s2


def test_compute_scope_differs_by_users():
    s1 = compute_scope(["alice", "bob"], "https://github.com")
    s2 = compute_scope(["alice", "charlie"], "https://github.com")
    assert s1 != s2


# --- load_snapshot ---


def test_load_snapshot_returns_none_when_missing(tmp_path):
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import load_snapshot

        assert load_snapshot(scope="abc123") is None


def test_load_snapshot_returns_data(tmp_path):
    payload = {
        "timestamp": "2026-04-05T12:00:00+00:00",
        "contributions": {"alice": {"2026": 50}},
    }
    _make_snapshot_file(tmp_path, payload, scope="abc123")
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import load_snapshot

        result = load_snapshot(scope="abc123")
    assert result["contributions"]["alice"]["2026"] == 50


def test_load_snapshot_context_id(tmp_path):
    payload = {
        "timestamp": "2026-04-05T12:00:00+00:00",
        "contributions": {"alice": {"2026": 50}},
    }
    _make_snapshot_file(tmp_path, payload, context_id="team-alpha")
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import load_snapshot

        result = load_snapshot(context_id="team-alpha")
    assert result["contributions"]["alice"]["2026"] == 50


def test_load_snapshot_returns_none_on_corrupt_json(tmp_path):
    snap = tmp_path / "snapshot-abc123.json"
    snap.write_text("not json{{")
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import load_snapshot

        assert load_snapshot(scope="abc123") is None


def test_load_snapshot_legacy_unscoped(tmp_path):
    """Unscoped load still reads the legacy snapshot.json."""
    payload = {
        "timestamp": "2026-04-05T12:00:00+00:00",
        "contributions": {"alice": {"2026": 50}},
    }
    _make_snapshot_file(tmp_path, payload)
    with patch("ghsnitch.snapshot._DEFAULT_SNAPSHOT_FILE", tmp_path / "snapshot.json"):
        from ghsnitch.snapshot import load_snapshot

        result = load_snapshot()
    assert result["contributions"]["alice"]["2026"] == 50


# --- save_snapshot ---


def test_save_snapshot_writes_file(tmp_path):
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import save_snapshot

        save_snapshot({"alice": {"2026": 100}}, scope="abc123")
    snap = tmp_path / "snapshot-abc123.json"
    data = json.loads(snap.read_text())
    assert data["contributions"]["alice"]["2026"] == 100
    assert "timestamp" in data


def test_save_snapshot_context_id(tmp_path):
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import save_snapshot

        save_snapshot({"bob": {"2026": 75}}, context_id="team-beta")
    snap = tmp_path / "snapshot-team-beta.json"
    assert snap.exists()


def test_save_snapshot_creates_parent_dirs(tmp_path):
    nested = tmp_path / "nested" / "dir"
    with patch("ghsnitch.snapshot.CACHE_DIR", nested):
        from ghsnitch.snapshot import save_snapshot

        save_snapshot({"bob": {"2026": 5}}, scope="abc123")
    assert (nested / "snapshot-abc123.json").exists()


def test_save_snapshot_persists_ranks(tmp_path):
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import save_snapshot

        save_snapshot(
            {"alice": {"2026": 100}},
            ranks={"alice": 1},
            positions={"alice": 1},
            scope="abc123",
        )
    snap = tmp_path / "snapshot-abc123.json"
    data = json.loads(snap.read_text())
    assert data["ranks"] == {"alice": 1}
    assert data["positions"] == {"alice": 1}


def test_save_snapshot_no_ranks_key_when_omitted(tmp_path):
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import save_snapshot

        save_snapshot({"alice": {"2026": 100}}, scope="abc123")
    snap = tmp_path / "snapshot-abc123.json"
    data = json.loads(snap.read_text())
    assert "ranks" not in data
    assert "positions" not in data


def test_save_snapshot_silently_ignores_os_error(tmp_path):
    snap = tmp_path / "snapshot-abc123.json"
    snap.mkdir()  # make it a directory so write fails
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import save_snapshot

        save_snapshot({"alice": {"2026": 10}}, scope="abc123")  # should not raise


# --- clear_snapshot ---


def test_clear_snapshot_scoped_deletes_only_that_scope(tmp_path):
    _make_snapshot_file(tmp_path, {"contributions": {}}, scope="aaa")
    _make_snapshot_file(tmp_path, {"contributions": {}}, scope="bbb")
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import clear_snapshot

        result = clear_snapshot(scope="aaa")
    assert result is True
    assert not (tmp_path / "snapshot-aaa.json").exists()
    assert (tmp_path / "snapshot-bbb.json").exists()


def test_clear_snapshot_no_scope_deletes_all(tmp_path):
    _make_snapshot_file(tmp_path, {"contributions": {}}, scope="aaa")
    _make_snapshot_file(tmp_path, {"contributions": {}}, scope="bbb")
    _make_snapshot_file(tmp_path, {"contributions": {}})  # legacy
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import clear_snapshot

        result = clear_snapshot()
    assert result is True
    assert not (tmp_path / "snapshot-aaa.json").exists()
    assert not (tmp_path / "snapshot-bbb.json").exists()
    assert not (tmp_path / "snapshot.json").exists()


def test_clear_snapshot_returns_true_when_no_file(tmp_path):
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        from ghsnitch.snapshot import clear_snapshot

        assert clear_snapshot(scope="nonexistent") is True


def test_clear_snapshot_returns_false_on_os_error(tmp_path):
    snap = tmp_path / "snapshot-abc123.json"
    snap.write_text("{}")

    def _bad_unlink(*_args, **_kwargs):
        raise OSError("permission denied")

    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        with patch.object(Path, "unlink", _bad_unlink):
            from ghsnitch.snapshot import clear_snapshot

            assert clear_snapshot(scope="abc123") is False


# --- clear_all_snapshots ---


def test_clear_all_snapshots(tmp_path):
    _make_snapshot_file(tmp_path, {}, "snapshot.json")
    _make_snapshot_file(tmp_path, {}, "snapshot-abc.json")
    _make_snapshot_file(tmp_path, {}, "snapshot-team-alpha.json")
    _make_snapshot_file(tmp_path, {}, "not-a-snapshot.txt")

    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        with patch(
            "ghsnitch.snapshot._DEFAULT_SNAPSHOT_FILE", tmp_path / "snapshot.json"
        ):
            from ghsnitch.snapshot import clear_all_snapshots

            assert clear_all_snapshots() is True

    assert not (tmp_path / "snapshot.json").exists()
    assert not (tmp_path / "snapshot-abc.json").exists()
    assert not (tmp_path / "snapshot-team-alpha.json").exists()
    assert (tmp_path / "not-a-snapshot.txt").exists()
