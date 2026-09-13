import logging
import sys
import tomllib
from pathlib import Path

from .xdg import CONFIG_DIR

__all__ = [
    "generate_default_config",
    "get_config_path",
    "load_config",
    "logger",
    "render_config",
    "update_config",
]

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
# Report on a named window instead of full years.
# Valid values: "week" (Mon→today), "month" (1st→today), "year" (Jan 1→today).
# When set, the 'years' option is ignored.
# period = "month"
# Show the last N calendar months as separate columns.
# last-months = 6
# Show the last N calendar quarters as separate columns.
# last-quarters = 4
# Show the last N ISO weeks as separate columns.
# last-weeks = 8

[network]
# GitHub base URL. Change this to target a GitHub Enterprise Server instance.
# github-url = "https://github.example.com"

[updates]
# Skip the automatic check for newer releases entirely.
# Also honoured via --no-update-check, or the GH_SNITCH_NO_UPDATE_CHECK
# environment variable set to any non-empty value.
# no-update-check = false

[display]
# Hide operatives whose current-year contribution count is below this threshold.
# Set to 0 (default) to show all operatives.
# min-contributions = 10

# Show a Total column (per-operative sum) and a Total footer row (per-year sum).
# totals = false

# Annotate each cell with the operative's percentage share of that year's total.
# percent = false

# Show a ± column with each operative's rank change since the last run.
# rank-delta = true

# Output format: table (default), json, csv, markdown, graph, stack, or xlsx.
# format = "table"

# Named cells (teams) — repeat --team <name> to surveil multiple groups.
# [teams.backend]
# users = ["octocat", "torvalds"]
#
# [teams.frontend]
# users = ["gvanrossum"]
"""


#: Kebab-case is the house style across the sibling CLIs (breakfast, five-clis,
#: jeeves). gh-snitch shipped these keys in snake_case first, so the old
#: spellings stay readable and warn. Maps (section, new name) -> old name.
_LEGACY_SPELLING = {
    ("surveillance", "last-months"): "last_months",
    ("surveillance", "last-quarters"): "last_quarters",
    ("surveillance", "last-weeks"): "last_weeks",
    ("network", "github-url"): "github_url",
    ("display", "min-contributions"): "min_contributions",
    ("display", "rank-delta"): "rank_delta",
    # Never a released spelling — but the options table documented it as
    # no_update_check from the day the key shipped, so configs written to the
    # docs exist in the wild. Aliasing it turns a silent no-op into a warning
    # and lets --update-config repair the file.
    ("updates", "no-update-check"): "no_update_check",
}


def _lookup(section_data, section_name, key):
    """Return (found, value) for *key*, honouring its deprecated spelling.

    If both spellings are present the kebab-case one wins outright and the old
    one is ignored, so a half-migrated file resolves predictably rather than
    depending on TOML ordering.
    """
    if key in section_data:
        return True, section_data[key]
    legacy = _LEGACY_SPELLING.get((section_name, key))
    if legacy and legacy in section_data:
        print(
            f"⚠️  Config key '{legacy}' is deprecated; rename it to '{key}' "
            f"under [{section_name}]. Run gh-snitch --update-config to do it "
            "automatically.",
            file=sys.stderr,
        )
        logger.warning("deprecated_config_key old=%s new=%s", legacy, key)
        return True, section_data[legacy]
    return False, None


def get_config_path():
    """Return the default path for the configuration file."""
    return CONFIG_DIR / "config.toml"


def load_config(config_path=None):
    """Load config from TOML file.

    Returns dict with keys 'users', 'years', 'teams', and more.
    Warns (does not error) if the file is not found.
    """
    path = Path(config_path) if config_path else get_config_path()
    config = {
        "users": [],
        "years": 3,
        "period": None,
        "last_months": None,
        "last_quarters": None,
        "last_weeks": None,
        "github_url": "https://github.com",
        "min_contributions": 0,
        "totals": False,
        "percent": False,
        "rank_delta": True,
        "output_format": "table",
        "no_update_check": False,
        "teams": {},
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
    if "period" in surveillance:
        config["period"] = surveillance["period"]
    found, value = _lookup(surveillance, "surveillance", "last-months")
    if found:
        config["last_months"] = int(value)
    found, value = _lookup(surveillance, "surveillance", "last-quarters")
    if found:
        config["last_quarters"] = int(value)
    found, value = _lookup(surveillance, "surveillance", "last-weeks")
    if found:
        config["last_weeks"] = int(value)
    found, value = _lookup(network, "network", "github-url")
    if found:
        config["github_url"] = value

    updates = data.get("updates", {})
    found, value = _lookup(updates, "updates", "no-update-check")
    if found:
        config["no_update_check"] = bool(value)

    display = data.get("display", {})
    found, value = _lookup(display, "display", "min-contributions")
    if found:
        config["min_contributions"] = value
    if "totals" in display:
        config["totals"] = bool(display["totals"])
    if "percent" in display:
        config["percent"] = bool(display["percent"])
    found, value = _lookup(display, "display", "rank-delta")
    if found:
        config["rank_delta"] = bool(value)
    if "format" in display:
        config["output_format"] = str(display["format"])

    teams_raw = data.get("teams", {})
    config["teams"] = {
        name: body["users"]
        for name, body in teams_raw.items()
        if isinstance(body, dict) and "users" in body
    }

    logger.debug(
        "config loaded users=%s years=%s github_url=%s",
        config["users"],
        config["years"],
        config["github_url"],
    )
    return config


def _toml_value(value):
    """Render *value* as a TOML scalar."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


#: Optional settings, in the order they are rendered, grouped by TOML section.
#: Each entry is (toml_key, cfg_key, default, example, comment). A setting that
#: differs from its default is written as a live key so it survives the round
#: trip; one still at its default is written as a commented example, so the
#: exported file keeps documenting what can be set.
_OPTIONAL_SETTINGS = (
    (
        "surveillance",
        (
            (
                "period",
                "period",
                None,
                "month",
                '"week", "month", or "year" — overrides years when set',
            ),
            (
                "last-months",
                "last_months",
                None,
                6,
                "last 6 calendar months as separate columns",
            ),
            (
                "last-quarters",
                "last_quarters",
                None,
                4,
                "last 4 calendar quarters as separate columns",
            ),
            (
                "last-weeks",
                "last_weeks",
                None,
                8,
                "last 8 ISO weeks as separate columns",
            ),
        ),
    ),
    (
        "network",
        (
            (
                "github-url",
                "github_url",
                "https://github.com",
                "https://github.example.com",
                "omit for github.com",
            ),
        ),
    ),
    (
        "updates",
        (
            (
                "no-update-check",
                "no_update_check",
                False,
                False,
                "skip the automatic check for newer releases",
            ),
        ),
    ),
    (
        "display",
        (
            (
                "format",
                "output_format",
                "table",
                "table",
                "table, json, csv, markdown, graph, stack, or xlsx",
            ),
            (
                "min-contributions",
                "min_contributions",
                0,
                10,
                "hide operatives below this threshold",
            ),
            ("totals", "totals", False, False, "show Total column and footer row"),
            (
                "percent",
                "percent",
                False,
                False,
                "annotate cells with (N%) share of period total",
            ),
            (
                "rank-delta",
                "rank_delta",
                True,
                True,
                "show ± rank-change column",
            ),
        ),
    ),
)

#: Column the trailing explanation comments line up on.
_COMMENT_COLUMN = 23


def _render_setting(toml_key, cfg_key, default, example, comment, cfg):
    """Render one optional setting as a live key or a commented example.

    A value that differs from its default is written live — without that,
    --export-config hands back a config with the setting reset, which is a
    silent data loss rather than a scaffold.
    """
    value = cfg.get(cfg_key, default)
    if value is not None and value != default:
        return f"{toml_key} = {_toml_value(value)}"
    body = f"# {toml_key} = {_toml_value(example)}"
    return f"{body:<{_COMMENT_COLUMN}} # {comment}"


def render_config(cfg: dict) -> str:
    """Return a TOML config string scaffolded from a loaded cfg dict.

    Every setting that differs from its default is written as a live key, so the
    output round-trips through load_config() with the same values. Settings still
    at their default are written as commented examples, keeping the exported file
    self-documenting.
    """
    users = cfg.get("users", [])
    users_toml = "[" + ", ".join(f'"{u}"' for u in users) + "]"
    years = cfg.get("years", 3)

    #: Keys that are always written live, keyed by the section they open.
    fixed = {
        "operatives": [f"users = {users_toml}"],
        "surveillance": [f"years = {years}"],
    }

    blocks = []
    for section_name, settings in _OPTIONAL_SETTINGS:
        lines = fixed.pop(section_name, [])
        lines += [_render_setting(*setting, cfg) for setting in settings]
        blocks.append(f"[{section_name}]\n" + "\n".join(lines))

    # Any section with no optional settings (operatives) still needs emitting,
    # ahead of the rest and in declaration order.
    leading = [f"[{name}]\n" + "\n".join(lines) for name, lines in fixed.items()]

    return "\n\n".join(leading + blocks) + "\n"


def generate_default_config(config_path=None, *, overwrite=False):
    """Write the default config template to disk.

    Args:
        config_path: Optional destination path. Uses the default config path when
            omitted.
        overwrite: Whether to replace an existing config file.

    Returns:
        Path: The config path written.

    Raises:
        FileExistsError: If the destination exists and overwrite is false.
    """
    path = Path(config_path) if config_path else get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with path.open(mode, encoding="utf-8") as config_file:
        config_file.write(_DEFAULT_CONFIG_TEMPLATE)
    return path


def _migrate_legacy_spellings(text):
    """Rewrite deprecated snake_case keys to kebab-case in *text*.

    Matches the key only at the start of a line, optionally commented, so a
    snake_case word inside a help comment or a string value is left alone.
    Returns (new_text, list_of_renames).
    """
    import re

    renamed = []
    for (section_name, new_key), old_key in _LEGACY_SPELLING.items():
        pattern = re.compile(rf"^(\s*#?\s*){re.escape(old_key)}(\s*=)", re.MULTILINE)
        text, count = pattern.subn(rf"\g<1>{new_key}\g<2>", text)
        if count:
            renamed.append(f"{section_name}.{old_key} -> {new_key}")
    return text, renamed


def _reparse(text, fallback):
    """Re-read *text* as TOML, falling back to *fallback* if it will not parse."""
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return fallback


def update_config(config_path=None):
    """Add missing keys from template to existing config.

    Also rewrites deprecated snake_case keys to their kebab-case spelling.

    Returns a list of keys added, plus any renames performed.
    """
    import re

    path = Path(config_path) if config_path else get_config_path()
    if not path.exists():
        return []

    # Use tomllib to find what's actually ACTIVE in current config
    try:
        with open(path, "rb") as f:
            active_data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        active_data = {}

    def get_all_keys(data, prefix=""):
        keys = set()
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict) and k != "teams":
                keys.update(get_all_keys(v, full_key))
            else:
                keys.add(full_key)
        return keys

    active_keys = get_all_keys(active_data)
    current_text = path.read_text()

    # Rewrite deprecated snake_case keys in place before looking for missing
    # ones. Without this the template's kebab-case key looks absent and gets
    # appended, leaving the file carrying both spellings of the same setting.
    current_text, renamed = _migrate_legacy_spellings(current_text)
    if renamed:
        active_data = _reparse(current_text, active_data)
        active_keys = get_all_keys(active_data)

    # Also detect commented-out keys so we don't re-add them
    commented_keys = set()
    current_section = None
    for line in current_text.splitlines():
        line = line.strip()
        if not line:
            continue
        section_match = re.match(r"^\[([\w.]+)\]", line)
        if section_match:
            current_section = section_match.group(1)
            continue
        # Match # key = or key =
        key_match = re.match(r"^(?:#\s*)?([\w-]+)\s*=", line)
        if key_match and current_section:
            commented_keys.add(f"{current_section}.{key_match.group(1)}")

    existing_keys = active_keys | commented_keys

    # Parse template to find all keys and their help blocks
    added_keys = []
    new_text = current_text

    template_sections = re.split(r"\n(?=\[[\w.]+\])", _DEFAULT_CONFIG_TEMPLATE)
    for section_block in template_sections:
        section_match = re.search(r"^\[([\w.]+)\]", section_block, re.MULTILINE)
        if not section_match:
            continue
        section_name = section_match.group(1)

        # Stop at commented-out section headers so their keys don't attribute here.
        commented_header = re.search(r"\n#\s*\[[\w.]+\]", section_block)
        if commented_header:
            section_block = section_block[: commented_header.start()]

        # Find all keys in this template section
        # Look for: # help text\n# key = value  OR  key = value
        # This regex catches:
        # 1. Any number of help/comment lines (Group 1)
        # 2. An optional '# ' prefix for the key (Group 2)
        # 3. The key name (Group 3)
        # 4. The value (Group 4)
        key_pattern = r"((?:# .*\n)*)(# )?([\w-]+)\s*=\s*(.*)"
        for match in re.finditer(key_pattern, section_block):
            help_text, _, key_name, default_val = match.groups()
            full_key = f"{section_name}.{key_name}"

            if full_key not in existing_keys:
                # Add to existing config as a comment
                addition = (
                    f"\n# {help_text.strip()}\n# {key_name} = {default_val} "
                    "(added by --update-config)\n"
                )

                section_header = f"[{section_name}]"
                if section_header in new_text:
                    # Append within section
                    parts = re.split(rf"(\[{section_name}\])", new_text)
                    # parts[2] is everything after [section]
                    next_section_match = re.search(r"\n\[[\w.]+\]", parts[2])
                    if next_section_match:
                        pos = next_section_match.start()
                        head = parts[2][:pos]
                        tail = parts[2][pos:]
                        parts[2] = head + addition + tail
                    else:
                        parts[2] = parts[2].rstrip() + "\n" + addition
                    new_text = "".join(parts)
                else:
                    # Section missing
                    new_text = new_text.rstrip() + f"\n\n[{section_name}]\n" + addition

                added_keys.append(full_key)
                existing_keys.add(full_key)

    # Renames alone are a reason to write, even when nothing was added.
    if added_keys or renamed:
        path.write_text(new_text)

    return added_keys + renamed
