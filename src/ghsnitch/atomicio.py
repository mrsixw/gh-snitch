"""Torn-write-safe file writes for the caches gh-snitch keeps on disk.

The guarantee is that a reader never observes a partially written file: the
destination is replaced by an atomic rename, so it holds either the whole old
contents or the whole new ones.

That is not the same as durability. Nothing here fsyncs, so a host crash or
power loss can still lose a rename the filesystem had not yet flushed. These
are caches — a lost update costs one re-fetch — and paying for fsync on every
snapshot write is not worth it. Anything that must survive a power cut needs
more than this module offers.
"""

import json
import os
import tempfile
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

    See the module docstring for what this does *not* promise: durability
    across a host crash needs fsync, which caches do not warrant.

    Args:
        path: Destination file path.
        text: Complete contents to write.
        encoding: Text encoding for both the write and the rename.

    Raises:
        OSError: If the write or the rename fails. The destination is left as
            it was, and the temp file is removed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp rather than a name built from the pid: threads share a pid, so two
    # concurrent writers in one process would otherwise pick the same temp path
    # and each could unlink or replace the other's file.
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f"{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(text)
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
