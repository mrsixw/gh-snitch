import logging
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def clean_ghsnitch_logger():
    """Remove handlers added by setup_logging() after each test."""
    yield
    log = logging.getLogger("ghsnitch")
    log.handlers.clear()


def test_setup_logging_creates_log_file(tmp_path):
    log_file = tmp_path / "run.log"
    with (
        patch("ghsnitch.logger.CACHE_DIR", tmp_path),
        patch("ghsnitch.logger._LOG_FILE", log_file),
    ):
        from ghsnitch.logger import setup_logging

        setup_logging()

    logging.getLogger("ghsnitch").info("test entry")
    assert log_file.exists()
    assert "test entry" in log_file.read_text()


def test_setup_logging_writes_debug_level(tmp_path):
    log_file = tmp_path / "run.log"
    with (
        patch("ghsnitch.logger.CACHE_DIR", tmp_path),
        patch("ghsnitch.logger._LOG_FILE", log_file),
    ):
        from ghsnitch.logger import setup_logging

        setup_logging()

    logging.getLogger("ghsnitch.api").debug("low-level trace")
    assert "low-level trace" in log_file.read_text()


def test_setup_logging_format(tmp_path):
    log_file = tmp_path / "run.log"
    with (
        patch("ghsnitch.logger.CACHE_DIR", tmp_path),
        patch("ghsnitch.logger._LOG_FILE", log_file),
    ):
        from ghsnitch.logger import setup_logging

        setup_logging()

    logging.getLogger("ghsnitch").info("check format")
    line = log_file.read_text().strip()
    # e.g. "2026-03-23T12:00:00 INFO     ghsnitch: check format"
    assert "INFO" in line
    assert "ghsnitch" in line
    assert "check format" in line


def test_setup_logging_silent_on_os_error(tmp_path):
    # Make CACHE_DIR a file so mkdir fails
    bad_dir = tmp_path / "notadir"
    bad_dir.write_text("blocker")
    with (
        patch("ghsnitch.logger.CACHE_DIR", bad_dir),
        patch("ghsnitch.logger._LOG_FILE", bad_dir / "run.log"),
    ):
        from ghsnitch.logger import setup_logging

        setup_logging()  # must not raise


def test_setup_logging_creates_cache_dir(tmp_path):
    nested = tmp_path / "a" / "b" / "gh-snitch"
    log_file = nested / "run.log"
    with (
        patch("ghsnitch.logger.CACHE_DIR", nested),
        patch("ghsnitch.logger._LOG_FILE", log_file),
    ):
        from ghsnitch.logger import setup_logging

        setup_logging()

    logging.getLogger("ghsnitch").info("hello")
    assert log_file.exists()
