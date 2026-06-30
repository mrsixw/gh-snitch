"""Update-check behaviour, exercised end-to-end through the CLI.

gh-snitch runs ``check_for_update()`` at the tail of a normal surveillance
pass (unless ``--no-update-check`` is given). These tests drive that path with
``click.testing.CliRunner`` and assert on observable CLI behaviour — whether the
"new intelligence package" nag is emitted and, crucially, that a broken cache or
a failing network call never crashes the run.
"""

import json
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError
from types import SimpleNamespace

import pytest
import requests
from click.testing import CliRunner

from ghsnitch import updater
from ghsnitch.cli import gh_snitch

RELEASES_URL = "https://api.github.com/repos/mrsixw/gh-snitch/releases/latest"
NAG_MARKER = "New intelligence package available"


def _graphql_response(login="alice", count=7):
    """Minimal GraphQL survey payload so a run completes and reaches the check."""
    return {
        "data": {
            "user_0": {
                "login": login,
                "contributionsCollection": {
                    "contributionCalendar": {"totalContributions": count}
                },
            }
        }
    }


@pytest.fixture
def cli(tmp_path, monkeypatch, requests_mock):
    """Run gh-snitch through CliRunner with the update check enabled.

    Isolates the updater cache, fakes the token, and mocks the GraphQL survey so
    a full pass completes and ends by calling ``check_for_update()``. Returns a
    namespace exposing ``run()``, the ``cache`` dir, and the ``requests_mock`` so
    individual tests can seed cache state or mock the release lookup.
    """
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(updater, "_CACHE_DIR", cache)
    monkeypatch.setattr("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token")

    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 1\n'
    )
    requests_mock.post("https://api.github.com/graphql", json=_graphql_response())

    runner = CliRunner()

    def run():
        # No --no-update-check: the run ends by calling check_for_update().
        return runner.invoke(gh_snitch, ["--config", str(config_file)])

    return SimpleNamespace(run=run, cache=cache, requests_mock=requests_mock)


def _iso(delta=timedelta(0)):
    return (datetime.now(timezone.utc) - delta).isoformat()


def _write_cache(cache, checked_at, latest_version="9999.0.0"):
    (cache / "update_check.json").write_text(
        json.dumps({"latest_version": latest_version, "checked_at": checked_at})
    )


# --- happy paths: the nag is shown only when a newer version is known ---


def test_cli_shows_update_nag_when_newer_version_cached(cli):
    _write_cache(cli.cache, _iso(timedelta(hours=1)), latest_version="9999.0.0")

    result = cli.run()

    assert result.exit_code == 0
    assert NAG_MARKER in result.output
    assert "9999.0.0" in result.output


def test_cli_no_nag_when_cached_version_not_newer(cli):
    _write_cache(cli.cache, _iso(timedelta(hours=1)), latest_version="0.0.1")

    result = cli.run()

    assert result.exit_code == 0
    assert NAG_MARKER not in result.output


# --- negative paths: a broken cache must never crash the run ---


def _cache_naive_timestamp(cache):
    # No timezone -> subtracting from an aware ``now`` raises TypeError (#92).
    _write_cache(cache, datetime.now().isoformat())


def _cache_malformed_json(cache):
    (cache / "update_check.json").write_text("{not valid json")


def _cache_missing_checked_at(cache):
    (cache / "update_check.json").write_text(json.dumps({"latest_version": "9.9.9"}))


def _cache_bad_timestamp(cache):
    _write_cache(cache, "not-a-timestamp")


def _cache_unreadable(cache):
    # A directory where the cache file is expected: exists() is True but
    # read_text() raises IsADirectoryError (an OSError subclass).
    (cache / "update_check.json").mkdir()


@pytest.mark.parametrize(
    "prepare",
    [
        _cache_naive_timestamp,
        _cache_malformed_json,
        _cache_missing_checked_at,
        _cache_bad_timestamp,
        _cache_unreadable,
    ],
    ids=[
        "naive-timestamp-issue-92",
        "malformed-json",
        "missing-checked-at",
        "bad-timestamp",
        "unreadable-cache",
    ],
)
def test_cli_survives_broken_update_cache(cli, prepare):
    """Every corrupt-cache shape is swallowed; the run exits cleanly.

    The ``naive-timestamp`` case is the regression for #92: before the fix a
    naive cached datetime raised an uncaught ``TypeError`` that surfaced as a
    non-zero CLI exit.
    """
    prepare(cli.cache)
    # Cache is unusable, so the reader reports a miss and falls back to the
    # network; mock that with an older release so no nag appears.
    cli.requests_mock.get(RELEASES_URL, json={"tag_name": "v0.0.1"})

    result = cli.run()

    assert result.exit_code == 0
    assert result.exception is None
    assert NAG_MARKER not in result.output


def test_cli_ignores_malformed_cached_version(cli):
    """A garbage cached version string parses to () and yields no nag."""
    _write_cache(cli.cache, _iso(timedelta(hours=1)), latest_version="not-a-version")

    result = cli.run()

    assert result.exit_code == 0
    assert NAG_MARKER not in result.output


# --- negative paths: a failing release lookup must never crash the run ---


def test_cli_survives_release_lookup_network_error(cli):
    cli.requests_mock.get(RELEASES_URL, exc=requests.exceptions.ConnectionError)

    result = cli.run()

    assert result.exit_code == 0
    assert result.exception is None
    assert NAG_MARKER not in result.output


def test_cli_survives_release_lookup_http_error(cli):
    cli.requests_mock.get(RELEASES_URL, status_code=404)

    result = cli.run()

    assert result.exit_code == 0
    assert NAG_MARKER not in result.output


def test_cli_survives_cache_write_failure(cli, tmp_path, monkeypatch):
    """An OSError while caching the fetched version is swallowed."""
    # Point the cache dir beneath a regular file so the write's mkdir raises
    # NotADirectoryError (an OSError subclass).
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file")
    monkeypatch.setattr(updater, "_CACHE_DIR", blocker / "cache")
    cli.requests_mock.get(RELEASES_URL, json={"tag_name": "v9999.0.0"})

    result = cli.run()

    assert result.exit_code == 0
    # The flow continued past the failed write and still surfaced the nag.
    assert NAG_MARKER in result.output


def test_cli_survives_package_not_found(cli, monkeypatch):
    """If the installed version can't be resolved, the run still exits cleanly."""

    def boom(_name):
        raise PackageNotFoundError("ghsnitch")

    monkeypatch.setattr(updater, "pkg_version", boom)
    _write_cache(cli.cache, _iso(timedelta(hours=1)), latest_version="9999.0.0")

    result = cli.run()

    assert result.exit_code == 0
    assert NAG_MARKER not in result.output


# --- _parse_version_tuple unit tests (pre-release handling) ---

from ghsnitch.updater import _parse_version_tuple  # noqa: E402


def test_parse_version_tuple_normal():
    assert _parse_version_tuple("1.2.3") == (1, 2, 3)


def test_parse_version_tuple_single():
    assert _parse_version_tuple("42") == (42,)


def test_parse_version_tuple_empty_string():
    assert _parse_version_tuple("") == ()


def test_parse_version_tuple_invalid():
    assert _parse_version_tuple("not-a-version") == ()


def test_parse_version_tuple_prerelease_alpha():
    assert _parse_version_tuple("1.0.0a1") == (1, 0, 0)


def test_parse_version_tuple_prerelease_dash():
    assert _parse_version_tuple("1.0.0-beta") == (1, 0, 0)


def test_parse_version_tuple_prerelease_rc():
    assert _parse_version_tuple("2.1.0rc3") == (2, 1, 0)


def test_parse_version_tuple_prerelease_compares_correctly():
    pre = _parse_version_tuple("1.0.0a1")
    release = _parse_version_tuple("1.0.0")
    assert pre == release


def test_parse_version_tuple_prerelease_does_not_trigger_false_update():
    installed = _parse_version_tuple("0.25.0a1")
    latest = _parse_version_tuple("0.25.0")
    assert not (latest > installed)
