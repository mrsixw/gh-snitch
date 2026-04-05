import os
from pathlib import Path


def get_cache_dir() -> Path:
    """Return the XDG-compliant cache directory for gh-snitch.

    Uses $XDG_CACHE_HOME if set, otherwise ~/.cache/gh-snitch.
    Appropriate for ephemeral data: update-check results, contribution snapshots.
    """
    xdg_cache = os.getenv("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "gh-snitch"
    return Path.home() / ".cache" / "gh-snitch"


def get_log_dir() -> Path:
    """Return the XDG-compliant log/state directory for gh-snitch.

    Uses $XDG_STATE_HOME if set, otherwise ~/.local/state/gh-snitch.
    Appropriate for persistent operational data: logs, history.
    """
    xdg_state = os.getenv("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state) / "gh-snitch"
    return Path.home() / ".local" / "state" / "gh-snitch"


CACHE_DIR = get_cache_dir()
LOG_DIR = get_log_dir()
