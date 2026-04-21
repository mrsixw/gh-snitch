import json
import logging
from datetime import datetime, timezone

from .xdg import CACHE_DIR

logger = logging.getLogger(__name__)

_DEFAULT_SNAPSHOT_FILE = CACHE_DIR / "snapshot.json"


def _get_snapshot_path(context_id=None):
    """Return the snapshot Path for a given context_id (e.g. team name)."""
    if context_id is None:
        return _DEFAULT_SNAPSHOT_FILE
    # Sanitize context_id to prevent path traversal, though it's likely safe.
    safe_id = "".join(
        c for c in str(context_id) if c.isalnum() or c in ("-", "_")
    ).strip()
    return CACHE_DIR / f"snapshot-{safe_id}.json"


def load_snapshot(context_id=None):
    """Load the saved contribution snapshot for a context.

    Returns the full data dict (with keys "timestamp" and "contributions") or
    None if no snapshot exists or it cannot be read.
    """
    try:
        path = _get_snapshot_path(context_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_snapshot(contributions, ranks=None, positions=None, context_id=None):
    """Persist contributions and optional leaderboard metadata to the cache.

    Args:
        contributions: dict[username, dict[year_label, int]]
        ranks: optional dict[username, int] mapping each operative to their rank
        positions: optional dict[username, float | int] mapping each operative
            to their tie-aware leaderboard movement position
        context_id: optional ID to partition the snapshot (e.g. team name)
    """
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "contributions": contributions,
        }
        if ranks is not None:
            data["ranks"] = ranks
        if positions is not None:
            data["positions"] = positions
        path = _get_snapshot_path(context_id)
        path.write_text(json.dumps(data))
    except OSError as e:
        logger.warning("failed to save snapshot: %s", e)


def clear_snapshot(context_id=None):
    """Delete the snapshot file. Returns True if cleared, False on error."""
    try:
        path = _get_snapshot_path(context_id)
        path.unlink(missing_ok=True)
        return True
    except OSError as e:
        logger.warning("failed to clear snapshot: %s", e)
        return False
