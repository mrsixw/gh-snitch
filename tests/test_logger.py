import json
from unittest.mock import patch


def test_log_run_writes_json_line(tmp_path):
    with (
        patch("ghsnitch.logger.CACHE_DIR", tmp_path),
        patch("ghsnitch.logger._LOG_FILE", tmp_path / "run.log"),
    ):
        from ghsnitch.logger import log_run

        log_run(
            operatives=["alice", "bob"],
            year_labels=["2026", "2025"],
            contributions={"alice": {"2026": 100, "2025": 380}},
            duration_seconds=1.234,
        )

    lines = (tmp_path / "run.log").read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["operatives"] == ["alice", "bob"]
    assert entry["year_labels"] == ["2026", "2025"]
    assert entry["contributions"] == {"alice": {"2026": 100, "2025": 380}}
    assert entry["duration_seconds"] == 1.234
    assert entry["error"] is None
    assert "timestamp" in entry


def test_log_run_records_error(tmp_path):
    with (
        patch("ghsnitch.logger.CACHE_DIR", tmp_path),
        patch("ghsnitch.logger._LOG_FILE", tmp_path / "run.log"),
    ):
        from ghsnitch.logger import log_run

        log_run([], [], {}, 0.5, error="connection refused")

    entry = json.loads((tmp_path / "run.log").read_text())
    assert entry["error"] == "connection refused"


def test_log_run_appends_multiple_entries(tmp_path):
    with (
        patch("ghsnitch.logger.CACHE_DIR", tmp_path),
        patch("ghsnitch.logger._LOG_FILE", tmp_path / "run.log"),
    ):
        from ghsnitch.logger import log_run

        log_run(["alice"], ["2026"], {}, 1.0)
        log_run(["bob"], ["2026"], {}, 2.0)

    lines = (tmp_path / "run.log").read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["operatives"] == ["alice"]
    assert json.loads(lines[1])["operatives"] == ["bob"]


def test_log_run_creates_cache_dir(tmp_path):
    nested = tmp_path / "a" / "b" / "gh-snitch"
    with (
        patch("ghsnitch.logger.CACHE_DIR", nested),
        patch("ghsnitch.logger._LOG_FILE", nested / "run.log"),
    ):
        from ghsnitch.logger import log_run

        log_run([], [], {}, 0.0)

    assert (nested / "run.log").exists()


def test_log_run_silent_on_os_error(tmp_path):
    # Point log file at an unwritable path (a directory, not a file)
    bad_log = tmp_path / "run.log"
    bad_log.mkdir()
    with (
        patch("ghsnitch.logger.CACHE_DIR", tmp_path),
        patch("ghsnitch.logger._LOG_FILE", bad_log),
    ):
        from ghsnitch.logger import log_run

        # Must not raise
        log_run([], [], {}, 0.0)
