import os
from pathlib import Path


def get_cache_dir() -> Path:
    """Return the XDG-compliant cache directory for gh-snitch."""
    xdg_cache = os.getenv("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "gh-snitch"
    return Path.home() / ".cache" / "gh-snitch"


CACHE_DIR = get_cache_dir()
