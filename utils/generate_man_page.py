"""Generate a man page for gh-snitch using click-man."""

import sys
from pathlib import Path

from click_man.core import write_man_pages

from ghsnitch.cli import gh_snitch

target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("man1")
target.mkdir(parents=True, exist_ok=True)
write_man_pages("gh-snitch", gh_snitch, target_dir=str(target))
