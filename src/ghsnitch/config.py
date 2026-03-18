import os
import sys
from pathlib import Path

import tomllib

_DEFAULT_CONFIG_TEMPLATE = """\
# gh-snitch configuration
# Spy-themed GitHub contribution surveillance

[operatives]
# List of GitHub usernames to surveil
# users = ["octocat", "torvalds", "gvanrossum"]
users = []

[surveillance]
# Number of prior complete years to include (in addition to the current year)
years = 3

[display]
# Future display options go here
"""


def get_config_dir():
    """Return the XDG-compliant config directory for gh-snitch."""
    xdg_config = os.getenv("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "gh-snitch"
    return Path.home() / ".config" / "gh-snitch"


def _default_config_path():
    return get_config_dir() / "config.toml"


def load_config(config_path=None):
    """Load config from TOML file. Returns dict with keys 'users' and 'years'.

    Warns (does not error) if the file is not found.
    """
    path = Path(config_path) if config_path else _default_config_path()
    config = {"users": [], "years": 3}

    if not path.exists():
        print(
            f"⚠️  No handler config found at {path}. "
            "Run gh-snitch --init-config to establish a cover.",
            file=sys.stderr,
        )
        return config

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        print(f"⚠️  Failed to read config at {path}: {e}", file=sys.stderr)
        return config

    operatives = data.get("operatives", {})
    surveillance = data.get("surveillance", {})

    if "users" in operatives:
        config["users"] = operatives["users"]
    if "years" in surveillance:
        config["years"] = surveillance["years"]

    return config


def generate_default_config(config_path=None):
    """Write default config template to disk. Returns the path used."""
    path = Path(config_path) if config_path else _default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DEFAULT_CONFIG_TEMPLATE)
    return path
