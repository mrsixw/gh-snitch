import json
from datetime import datetime, timezone

from .updater import CACHE_DIR

_LOG_FILE = CACHE_DIR / "run.log"


def log_run(operatives, year_labels, contributions, duration_seconds, error=None):
    """Append a structured JSON log entry for this run to the cache log file.

    Each line is a self-contained JSON object (JSON Lines format):
      {
        "timestamp":        ISO 8601 UTC timestamp,
        "operatives":       list of surveilled usernames,
        "year_labels":      list of year strings, current year first,
        "contributions":    {username: {year: count, ...}, ...},
        "duration_seconds": wall-clock time for the API sweep,
        "error":            error message string, or null on success
      }

    Silently does nothing if the log file cannot be written — a logging
    failure must never surface to the user.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operatives": operatives,
        "year_labels": year_labels,
        "contributions": contributions,
        "duration_seconds": round(duration_seconds, 3),
        "error": error,
    }
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass
