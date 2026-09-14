"""Crash-safe file writes for the caches gh-snitch keeps on disk."""

import json
import os
from pathlib import Path

__all__ = ["write_json_atomic", "write_text_atomic"]


def write_text_atomic(path, text, encoding="utf-8"):
    """Write text so readers see either the old file or the new one.

    ``Path.write_text`` truncates the target before it writes. A crash, a
    Ctrl+C, or a second gh-snitch run landing in the same moment therefore
    leaves a half-written file behind — and because the readers here treat
    unparsable cache as absent, that damage is silent: movement history simply
    resets with nothing said.

    Writing a sibling temp file and renaming it avoids the window entirely.
    ``os.replace`` is atomic on POSIX and Windows alike, so the target is never
    observed partially written. The temp file is created in the destination
    directory because a rename across filesystems is not atomic — and, on some
    platforms, not permitted.

    Args:
        path: Destination file path.
        text: Complete contents to write.
        encoding: Text encoding for both the write and the rename.

    Raises:
        OSError: If the write or the rename fails. The destination is left as
            it was, and the temp file is removed.
    """
    path = Path(path)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp_path.write_text(text, encoding=encoding)
        os.replace(tmp_path, path)
    except OSError:
        # A temp file left behind would accumulate silently, one per failure.
        tmp_path.unlink(missing_ok=True)
        raise


def write_json_atomic(path, data, encoding="utf-8"):
    """Serialise ``data`` to JSON and write it atomically.

    Serialising before opening anything matters: a value JSON cannot encode
    raises here, leaving the existing file untouched, rather than after the
    destination has already been replaced.

    Args:
        path: Destination file path.
        data: JSON-serialisable object.
        encoding: Text encoding for the write.

    Raises:
        OSError: If the write or the rename fails.
        TypeError: If ``data`` is not JSON-serialisable.
    """
    write_text_atomic(path, json.dumps(data), encoding=encoding)
