import json
import logging
from datetime import datetime, timezone

from .xdg import CACHE_DIR

logger = logging.getLogger(__name__)

_SNAPSHOT_FILE = CACHE_DIR / "snapshot.json"


def load_snapshot():
    """Load the saved contribution snapshot.

    Returns the full data dict (with keys "timestamp" and "contributions") or
    None if no snapshot exists or it cannot be read.
    """
    try:
        if not _SNAPSHOT_FILE.exists():
            return None
        return json.loads(_SNAPSHOT_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_snapshot(contributions):
    """Persist contributions to the snapshot cache.

    Args:
        contributions: dict[username, dict[year_label, int]]
    """
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _SNAPSHOT_FILE.write_text(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "contributions": contributions,
                }
            )
        )
    except OSError as e:
        logger.warning("failed to save snapshot: %s", e)


def clear_snapshot():
    """Delete the snapshot file. Returns True if cleared, False on error."""
    try:
        _SNAPSHOT_FILE.unlink(missing_ok=True)
        return True
    except OSError as e:
        logger.warning("failed to clear snapshot: %s", e)
        return False
