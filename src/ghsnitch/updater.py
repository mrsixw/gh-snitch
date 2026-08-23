import json
import os
import re
from datetime import datetime, timezone
from enum import Enum, auto
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path

import requests

from .api import SECRET_GITHUB_TOKEN
from .xdg import CACHE_DIR

__all__ = [
    "UpdateStatus",
    "check_for_update",
    "get_latest_version",
    "perform_update",
]

_UPDATE_CHECK_REPO = "mrsixw/gh-snitch"
_PACKAGE_NAME = "ghsnitch"
_BINARY_NAME = "gh-snitch"
_RELEASE_ASSET_URL = (
    f"https://github.com/{_UPDATE_CHECK_REPO}/releases/latest/download/{_BINARY_NAME}"
)

_CACHE_DIR = CACHE_DIR  # backwards-compatible alias
_CACHE_TTL_SECONDS = 86400  # 24 hours


class UpdateStatus(Enum):
    """Outcome of a :func:`perform_update` attempt.

    The values are deliberately meaningless — nothing should serialise or
    compare against them, so call sites use ``is`` against the members.
    """

    UPDATED = auto()
    UP_TO_DATE = auto()
    UNKNOWN = auto()
    ERROR = auto()


def _read_version_cache():
    cache_file = _CACHE_DIR / "update_check.json"
    try:
        if not cache_file.exists():
            return None
        data = json.loads(cache_file.read_text())
        cached_at = datetime.fromisoformat(data["checked_at"])
        age = (datetime.now(timezone.utc) - cached_at).total_seconds()
        if age > _CACHE_TTL_SECONDS:
            return None
        return data.get("latest_version")
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def _write_version_cache(latest_version):
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = _CACHE_DIR / "update_check.json"
        cache_file.write_text(
            json.dumps(
                {
                    "latest_version": latest_version,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        )
    except OSError:
        pass


def get_latest_version():
    cached = _read_version_cache()
    if cached:
        return cached
    try:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if SECRET_GITHUB_TOKEN:
            headers["Authorization"] = f"token {SECRET_GITHUB_TOKEN}"
        resp = requests.get(
            f"https://api.github.com/repos/{_UPDATE_CHECK_REPO}/releases/latest",
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        tag = resp.json().get("tag_name", "")
        latest = tag.lstrip("v")
        _write_version_cache(latest)
        return latest
    except requests.exceptions.RequestException:
        return None


def _parse_version_tuple(version_str):
    try:
        parts = []
        for segment in version_str.split("."):
            m = re.match(r"\d+", segment)
            if not m:
                break
            parts.append(int(m.group()))
        return tuple(parts)
    except (ValueError, AttributeError):
        return ()


def check_for_update():
    try:
        current = pkg_version("ghsnitch")
        latest = get_latest_version()
        if not latest:
            return None
        if _parse_version_tuple(latest) > _parse_version_tuple(current):
            return (
                f"📬 New intelligence package available: v{latest}. "
                f"Update at: https://github.com/{_UPDATE_CHECK_REPO}/releases/latest"
            )
        return None
    except PackageNotFoundError:
        return None


def perform_update(executable_path) -> tuple[UpdateStatus, str, str | None]:
    """Download the latest gh-snitch release and replace executable_path in place.

    Returns (status, current_version, detail):
      - UPDATED: executable_path now holds the release named by detail.
      - UP_TO_DATE: current_version already matches or exceeds detail (latest).
      - UNKNOWN: the latest version could not be determined; detail is None.
      - ERROR: the download or install failed; detail carries the error message.
    """
    current = pkg_version(_PACKAGE_NAME)
    executable_path = Path(executable_path)
    if executable_path.suffix == ".py":
        # Invoked from a source checkout (python -m <pkg>.cli), not an installed
        # release. Writing a downloaded binary here would destroy the source.
        return (
            UpdateStatus.ERROR,
            current,
            f"{executable_path} is a source file, not an installed binary — "
            "install a release before updating.",
        )

    latest = get_latest_version()
    if not latest:
        return UpdateStatus.UNKNOWN, current, None
    # Same comparison check_for_update() uses, so the passive notice and this
    # command can never disagree about whether an update exists.
    if not _parse_version_tuple(latest) > _parse_version_tuple(current):
        return UpdateStatus.UP_TO_DATE, current, latest

    # Download to a sibling and os.replace() it into position: the rename is
    # atomic within a filesystem, so an interrupted download can never leave a
    # half-written binary where the working one used to be.
    tmp_path = executable_path.with_name(executable_path.name + ".new")
    try:
        with requests.get(_RELEASE_ASSET_URL, timeout=30, stream=True) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=65536):
                    fh.write(chunk)
        tmp_path.chmod(0o755)
        os.replace(tmp_path, executable_path)
    except (OSError, requests.exceptions.RequestException) as exc:
        return UpdateStatus.ERROR, current, str(exc)
    finally:
        # Also covers KeyboardInterrupt mid-download, which the except above
        # deliberately does not catch. A successful os.replace leaves nothing
        # to remove, so this is a no-op on the happy path.
        tmp_path.unlink(missing_ok=True)
    return UpdateStatus.UPDATED, current, latest
