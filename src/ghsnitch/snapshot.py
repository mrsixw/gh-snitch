import hashlib
import json
import logging
from datetime import datetime, timezone

from .xdg import CACHE_DIR

logger = logging.getLogger(__name__)

_LEGACY_SNAPSHOT_FILE = CACHE_DIR / "snapshot.json"


def compute_scope(usernames, github_url):
    """Return a short hash of the user cohort + instance for snapshot scoping."""
    user_key = ",".join(sorted(usernames or []))
    url_key = github_url.lower().rstrip("/")
    combined = f"{user_key}|{url_key}"
    return hashlib.sha256(combined.encode()).hexdigest()[:12]


def _get_snapshot_path(scope=None, context_id=None):
    """Return the snapshot Path for a given scope and/or context_id."""
    if context_id:
        # Sanitize context_id (e.g. team name)
        safe_id = "".join(c for c in str(context_id) if c.isalnum() or c in ("-", "_"))
        return CACHE_DIR / f"snapshot-{safe_id}.json"
    if scope:
        return CACHE_DIR / f"snapshot-{scope}.json"
    return _LEGACY_SNAPSHOT_FILE


def load_snapshot(scope=None, context_id=None):
    """Load the saved contribution snapshot for a scope.

    Returns the full data dict (with keys "timestamp" and "contributions") or
    None if no snapshot exists or it cannot be read.
    """
    try:
        path = _get_snapshot_path(scope, context_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_snapshot(
    contributions, ranks=None, positions=None, scope=None, context_id=None
):
    """Persist contributions and optional leaderboard metadata to the cache.

    Args:
        contributions: dict[username, dict[year_label, int]]
        ranks: optional dict[username, int] mapping each operative to their rank
        positions: optional dict[username, float | int] mapping each operative
            to their tie-aware leaderboard movement position
        scope: optional cohort scope hash
        context_id: optional explicit ID (e.g. team name)
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
        path = _get_snapshot_path(scope, context_id)
        path.write_text(json.dumps(data))
    except OSError as e:
        logger.warning("failed to save snapshot: %s", e)


def clear_snapshot(scope=None, context_id=None):
    """Delete the specific snapshot file. Returns True if cleared."""
    try:
        path = _get_snapshot_path(scope, context_id)
        path.unlink(missing_ok=True)
        return True
    except OSError as e:
        logger.warning("failed to clear snapshot: %s", e)
        return False


def clear_all_snapshots():
    """Delete ALL snapshot files (legacy, scoped, and team-specific)."""
    count = 0
    try:
        # Legacy
        if _LEGACY_SNAPSHOT_FILE.exists():
            _LEGACY_SNAPSHOT_FILE.unlink()
            count += 1
        # New pattern
        for p in CACHE_DIR.glob("snapshot-*.json"):
            p.unlink()
            count += 1
        return True
    except OSError as e:
        logger.warning("failed to clear all snapshots: %s", e)
        return False
