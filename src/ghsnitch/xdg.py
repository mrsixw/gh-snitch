import os
from pathlib import Path


def _xdg_override(env_var: str) -> Path | None:
    """Return the env var value as a Path only if it is set to an absolute path.

    The XDG Base Directory Specification requires that $XDG_*_HOME values be
    absolute paths; relative values must be ignored and the default used instead.
    """
    val = os.getenv(env_var)
    if val and Path(val).is_absolute():
        return Path(val)
    return None


def get_config_dir() -> Path:
    """Return the XDG-compliant config directory for gh-snitch.

    Uses $XDG_CONFIG_HOME if set to an absolute path, otherwise ~/.config/gh-snitch.
    Appropriate for user configuration files.
    """
    override = _xdg_override("XDG_CONFIG_HOME")
    if override:
        return override / "gh-snitch"
    return Path.home() / ".config" / "gh-snitch"


def get_cache_dir() -> Path:
    """Return the XDG-compliant cache directory for gh-snitch.

    Uses $XDG_CACHE_HOME if set to an absolute path, otherwise ~/.cache/gh-snitch.
    Appropriate for ephemeral data: update-check results, contribution snapshots.
    """
    override = _xdg_override("XDG_CACHE_HOME")
    if override:
        return override / "gh-snitch"
    return Path.home() / ".cache" / "gh-snitch"


def get_log_dir() -> Path:
    """Return the XDG-compliant log/state directory for gh-snitch.

    Uses $XDG_STATE_HOME if set to an absolute path, otherwise ~/.local/state/gh-snitch.
    Appropriate for persistent operational data: logs, history.
    """
    override = _xdg_override("XDG_STATE_HOME")
    if override:
        return override / "gh-snitch"
    return Path.home() / ".local" / "state" / "gh-snitch"


CONFIG_DIR = get_config_dir()
CACHE_DIR = get_cache_dir()
LOG_DIR = get_log_dir()
