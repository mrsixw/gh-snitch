import logging

from .xdg import LOG_DIR

_LOG_FILE = LOG_DIR / "run.log"
_FMT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%dT%H:%M:%S"


def setup_logging():
    """Attach a DEBUG-level file handler to the ghsnitch logger.

    Writes a plain-text trace log to ~/.local/state/gh-snitch/run.log so that
    the full execution flow is available for post-hoc debugging without
    any output appearing in the terminal.

    Silently does nothing if the log file cannot be opened — a logging
    failure must never surface to the user.
    """
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(_LOG_FILE, mode="w", encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))
        logger = logging.getLogger("ghsnitch")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.propagate = False
    except OSError:
        pass
