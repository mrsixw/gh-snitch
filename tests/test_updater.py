import json
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError

import pytest
import requests

from ghsnitch import updater


@pytest.fixture
def cache_dir(monkeypatch, tmp_path):
    """Point the updater's cache directory at a temp location."""
    target = tmp_path / "cache"
    target.mkdir()
    monkeypatch.setattr(updater, "_CACHE_DIR", target)
    return target


def _write_cache(cache_dir, checked_at, latest_version="9.9.9"):
    (cache_dir / "update_check.json").write_text(
        json.dumps({"latest_version": latest_version, "checked_at": checked_at})
    )


def test_read_version_cache_naive_datetime_returns_none(cache_dir):
    """A naive cached timestamp must not raise TypeError (regression for #92).

    Subtracting an offset-naive datetime from the offset-aware ``datetime.now``
    raises ``TypeError``; the cache reader should swallow it and report a miss.
    """
    naive = datetime.now().replace(tzinfo=None).isoformat()
    _write_cache(cache_dir, naive)

    assert updater._read_version_cache() is None


def test_read_version_cache_fresh_returns_version(cache_dir):
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _write_cache(cache_dir, recent, latest_version="1.2.3")

    assert updater._read_version_cache() == "1.2.3"


def test_read_version_cache_expired_returns_none(cache_dir):
    stale = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    _write_cache(cache_dir, stale)

    assert updater._read_version_cache() is None


def test_read_version_cache_missing_file_returns_none(cache_dir):
    assert updater._read_version_cache() is None


# --- negative paths: each exception branch in _read_version_cache ---


def test_read_version_cache_malformed_json_returns_none(cache_dir):
    """Corrupt cache contents (JSONDecodeError) report a miss, not a crash."""
    (cache_dir / "update_check.json").write_text("{not valid json")

    assert updater._read_version_cache() is None


def test_read_version_cache_missing_checked_at_returns_none(cache_dir):
    """A cache without the ``checked_at`` key (KeyError) reports a miss."""
    (cache_dir / "update_check.json").write_text(
        json.dumps({"latest_version": "1.2.3"})
    )

    assert updater._read_version_cache() is None


def test_read_version_cache_bad_timestamp_returns_none(cache_dir):
    """An unparseable timestamp (ValueError from fromisoformat) reports a miss."""
    _write_cache(cache_dir, "not-a-timestamp")

    assert updater._read_version_cache() is None


def test_read_version_cache_unreadable_file_returns_none(cache_dir):
    """An OSError while reading the cache (here a directory) reports a miss."""
    # A directory at the cache path: exists() is True but read_text() raises
    # IsADirectoryError (an OSError subclass).
    (cache_dir / "update_check.json").mkdir()

    assert updater._read_version_cache() is None


# --- negative paths: _write_version_cache swallows OSError ---


def test_write_version_cache_swallows_oserror(monkeypatch, tmp_path):
    """A filesystem failure while writing the cache must not propagate."""
    # Place the cache dir beneath a regular file so mkdir() raises
    # NotADirectoryError (an OSError subclass).
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("i am a file")
    monkeypatch.setattr(updater, "_CACHE_DIR", blocker / "cache")

    # Should not raise.
    updater._write_version_cache("1.2.3")


# --- negative paths: get_latest_version on network failure ---


def test_get_latest_version_network_error_returns_none(cache_dir, monkeypatch):
    """A RequestException during the release lookup yields None, not a crash."""

    def boom(*args, **kwargs):
        raise requests.exceptions.RequestException("offline")

    monkeypatch.setattr(updater.requests, "get", boom)

    assert updater.get_latest_version() is None


def test_get_latest_version_http_error_returns_none(cache_dir, monkeypatch):
    """A non-2xx response (raise_for_status) is treated as no result."""

    class FakeResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError("404")

        def json(self):  # pragma: no cover - never reached
            return {}

    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: FakeResponse())

    assert updater.get_latest_version() is None


# --- negative paths: _parse_version_tuple on garbage input ---


def test_parse_version_tuple_non_numeric_returns_empty():
    """Non-numeric segments (ValueError) collapse to an empty tuple."""
    assert updater._parse_version_tuple("1.2.x") == ()


def test_parse_version_tuple_none_returns_empty():
    """A None version (AttributeError on .split) collapses to an empty tuple."""
    assert updater._parse_version_tuple(None) == ()


# --- negative paths: check_for_update when the package is not installed ---


def test_check_for_update_package_not_found_returns_none(monkeypatch):
    """PackageNotFoundError (package not installed) is handled gracefully."""

    def boom(_name):
        raise PackageNotFoundError("ghsnitch")

    monkeypatch.setattr(updater, "pkg_version", boom)

    assert updater.check_for_update() is None


def test_check_for_update_no_latest_returns_none(monkeypatch):
    """When the latest version cannot be determined, no nudge is returned."""
    monkeypatch.setattr(updater, "pkg_version", lambda _name: "1.0.0")
    monkeypatch.setattr(updater, "get_latest_version", lambda: None)

    assert updater.check_for_update() is None
