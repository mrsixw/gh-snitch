import logging
import sys
import tomllib
from pathlib import Path

from .xdg import CONFIG_DIR

logger = logging.getLogger(__name__)

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

[network]
# GitHub base URL. Change this to target a GitHub Enterprise Server instance.
# github_url = "https://github.example.com"

[display]
# Hide operatives whose current-year contribution count is below this threshold.
# Set to 0 (default) to show all operatives.
# min_contributions = 10

# Show a Total column (per-operative sum) and a Total footer row (per-year sum).
# totals = false

# Annotate each cell with the operative's percentage share of that year's total.
# percent = false

# Show a ± column with each operative's rank change since the last run.
# rank_delta = false
"""


def _default_config_path():
    return CONFIG_DIR / "config.toml"


def load_config(config_path=None):
    """Load config from TOML file. Returns dict with keys 'users' and 'years'.

    Warns (does not error) if the file is not found.
    """
    path = Path(config_path) if config_path else _default_config_path()
    config = {
        "users": [],
        "years": 3,
        "github_url": "https://github.com",
        "min_contributions": 0,
        "totals": False,
        "percent": False,
        "rank_delta": False,
    }
    logger.debug("loading config from %s", path)

    if not path.exists():
        logger.debug("config not found at %s, using defaults", path)
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
        logger.warning("failed to read config at %s: %s", path, e)
        print(f"⚠️  Failed to read config at {path}: {e}", file=sys.stderr)
        return config

    operatives = data.get("operatives", {})
    surveillance = data.get("surveillance", {})

    network = data.get("network", {})

    if "users" in operatives:
        config["users"] = operatives["users"]
    if "years" in surveillance:
        config["years"] = surveillance["years"]
    if "github_url" in network:
        config["github_url"] = network["github_url"]

    display = data.get("display", {})
    if "min_contributions" in display:
        config["min_contributions"] = display["min_contributions"]
    if "totals" in display:
        config["totals"] = bool(display["totals"])
    if "percent" in display:
        config["percent"] = bool(display["percent"])
    if "rank_delta" in display:
        config["rank_delta"] = bool(display["rank_delta"])

    logger.debug(
        "config loaded users=%s years=%s github_url=%s",
        config["users"],
        config["years"],
        config["github_url"],
    )
    return config


def generate_default_config(config_path=None):
    """Write default config template to disk. Returns the path used."""
    path = Path(config_path) if config_path else _default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DEFAULT_CONFIG_TEMPLATE)
    return path
