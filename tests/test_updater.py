import json
from datetime import datetime, timedelta, timezone

import pytest

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
