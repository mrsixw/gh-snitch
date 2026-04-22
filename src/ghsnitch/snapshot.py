import hashlib
import json
import logging
from datetime import datetime, timezone

from .xdg import CACHE_DIR

logger = logging.getLogger(__name__)

_SNAPSHOT_FILE = CACHE_DIR / "snapshot.json"

_SCOPE_HASH_LENGTH = 12


def compute_scope(users, github_url="https://github.com"):
    """Derive a snapshot scope key from the resolved operative list.

    The scope is a short hex digest of the normalised usernames and GitHub URL,
    ensuring each unique cohort + instance combination gets its own snapshot.
    """
    normalised = sorted(u.lower() for u in users)
    payload = f"{','.join(normalised)}|{github_url}"
    return hashlib.sha256(payload.encode()).hexdigest()[:_SCOPE_HASH_LENGTH]


def _snapshot_path(scope=None):
    """Return the snapshot file path for the given scope."""
    if scope is None:
        return _SNAPSHOT_FILE
    return CACHE_DIR / f"snapshot-{scope}.json"


def load_snapshot(scope=None):
    """Load the saved contribution snapshot for *scope*.

    Returns the full data dict (with keys "timestamp" and "contributions") or
    None if no snapshot exists or it cannot be read.
    """
    path = _snapshot_path(scope)
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_snapshot(contributions, ranks=None, positions=None, scope=None):
    """Persist contributions and optional leaderboard metadata to the cache.

    Args:
        contributions: dict[username, dict[year_label, int]]
        ranks: optional dict[username, int] mapping each operative to their rank
        positions: optional dict[username, float | int] mapping each operative
            to their tie-aware leaderboard movement position
        scope: optional scope key from :func:`compute_scope`
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
        _snapshot_path(scope).write_text(json.dumps(data))
    except OSError as e:
        logger.warning("failed to save snapshot: %s", e)


def clear_snapshot(scope=None):
    """Delete snapshot files. Returns True if cleared, False on error.

    When *scope* is given, only that scope's snapshot is removed.
    When *scope* is ``None``, **all** snapshot files (scoped and legacy) are
    removed — this is the behaviour behind ``--reset-snapshot``.
    """
    try:
        if scope is not None:
            _snapshot_path(scope).unlink(missing_ok=True)
        else:
            for path in CACHE_DIR.glob("snapshot*.json"):
                path.unlink(missing_ok=True)
        return True
    except OSError as e:
        logger.warning("failed to clear snapshot: %s", e)
        return False
