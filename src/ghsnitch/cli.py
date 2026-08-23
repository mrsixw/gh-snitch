import hashlib
import importlib.metadata
import logging
import os
import shutil
import sys
import time
from enum import StrEnum, auto
from pathlib import Path

import click
import requests
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

from . import config as config_module
from .api import (
    SECRET_GITHUB_TOKEN,
    VALID_PERIODS,
    GitHubGraphQLError,
    GitHubGraphQLRateLimitError,
    GitHubGraphQLResourceLimitError,
    configure_api_stats,
    current_year_fraction,
    fetch_contributions,
    get_api_stats,
    get_custom_range,
    get_graphql_rate_limit,
    get_period_range,
    get_rolling_month_ranges,
    get_rolling_week_ranges,
    get_year_ranges,
)
from .config import generate_default_config, get_config_path, load_config
from .logger import setup_logging
from .snapshot import (
    clear_all_snapshots,
    compute_scope,
    load_snapshot,
    save_snapshot,
)
from .ui import (
    render_csv,
    render_graph,
    render_json,
    render_markdown,
    render_stack,
    render_table,
)
from .updater import UpdateStatus, check_for_update, perform_update

__all__ = [
    "VALID_FORMATS",
    "Shell",
    "completions",
    "gh_snitch",
    "update",
]

VALID_FORMATS = ("table", "json", "csv", "markdown", "graph", "stack")


class Shell(StrEnum):
    """A shell that ``completions`` can emit a completion script for.

    ``StrEnum`` + ``auto()`` yields the lowercase member name as the value, so
    members pass straight into Click's completion machinery and into f-strings
    without a trail of ``.value``.
    """

    BASH = auto()
    ZSH = auto()
    FISH = auto()


# Click matches enum choices on member *names*, so click.Choice(Shell) would
# demand "BASH" rather than "bash" — pass the values explicitly instead.
_SHELL_CHOICES = [shell.value for shell in Shell]

_NATO_ALPHABET = [
    "Alpha",
    "Bravo",
    "Charlie",
    "Delta",
    "Echo",
    "Foxtrot",
    "Golf",
    "Hotel",
    "India",
    "Juliet",
    "Kilo",
    "Lima",
    "Mike",
    "November",
    "Oscar",
    "Papa",
    "Quebec",
    "Romeo",
    "Sierra",
    "Tango",
    "Uniform",
    "Victor",
    "Whiskey",
    "X-ray",
    "Yankee",
    "Zulu",
]

logger = logging.getLogger(__name__)


def _env_flag_is_set(name):
    """Report whether an environment variable is set to any non-empty value.

    This is the no-color.org convention gh-snitch already follows for
    NO_COLOR: presence is the signal and the value is deliberately ignored,
    so GH_SNITCH_NO_UPDATE_CHECK=0 disables the check just as =1 does.

    Click's envvar= on a boolean flag cannot express this. It routes the value
    through the BOOL converter, so an unrecognised one aborts the whole run —
    a typo in a shell profile would break the tool rather than be ignored.
    """
    return bool(os.environ.get(name))


def _bounded_error_detail(error, limit=200):
    """Return a concise single-line detail for terminal error messages.

    Args:
        error: Exception or value to render.
        limit: Maximum number of characters to return.

    Returns:
        str: Normalized, optionally truncated error detail.
    """
    detail = " ".join(str(error).split()) or type(error).__name__
    if len(detail) > limit:
        return f"{detail[: limit - 3]}..."
    return detail


def _print_api_stats_summary(run_start, operative_count, stats, rate_limit):
    """Print a spy-themed API diagnostics summary to stderr.

    Args:
        run_start: Monotonic timestamp captured when the command started.
        operative_count: Number of requested operatives in the completed sweep.
        stats: Snapshot returned by :func:`get_api_stats`.
        rate_limit: GraphQL ``rateLimit`` data, or ``None`` when unavailable.
    """
    elapsed = time.monotonic() - run_start
    lines = [
        click.style("🛰️  API intelligence", fg="cyan", bold=True),
        f"  Total elapsed:    {elapsed:.2f}s",
        f"  Operatives:       {operative_count}",
        f"  GraphQL calls:    {stats['graphql_calls']}",
    ]

    rate_lines = 0
    if rate_limit:
        remaining = rate_limit.get("remaining")
        used = rate_limit.get("used")
        reset_at = rate_limit.get("resetAt")
        if remaining is not None:
            lines.append(f"  GQL rate limit:   {remaining} points remaining")
            rate_lines += 1
        if used is not None:
            lines.append(f"  GQL points used:  {used}")
            rate_lines += 1
        if reset_at:
            lines.append(f"  GQL rate resets:  {reset_at}")
            rate_lines += 1
    if rate_lines == 0:
        lines.append("  GQL rate status:  unavailable")

    click.echo("\n".join(lines), err=True)


def _compute_rank_metadata(rows, current_year_label):
    """Return display ranks and movement positions for the leaderboard.

    Args:
        rows: iterable of contribution rows with a ``username`` key
        current_year_label: year label used to sort the leaderboard

    Returns:
        tuple[dict[str, int], dict[str, int]]: competition ranks for display and
        visible ranks for movement tracking
    """
    sorted_rows = sorted(
        rows, key=lambda r: (-r.get(current_year_label, 0), r["username"])
    )
    ranks = {}
    positions = {}
    i = 0
    while i < len(sorted_rows):
        current_count = sorted_rows[i].get(current_year_label, 0)
        group_end = i + 1
        while (
            group_end < len(sorted_rows)
            and sorted_rows[group_end].get(current_year_label, 0) == current_count
        ):
            group_end += 1

        competition_rank = i + 1
        for row in sorted_rows[i:group_end]:
            username = row["username"]
            ranks[username] = competition_rank
            positions[username] = competition_rank

        i = group_end
    return ranks, positions


def _get_snapshot_ranks(snapshot, current_year_label):
    """Return visible ranks for a previous snapshot if possible.

    Persisted ranks are preferred over legacy movement positions so the ±
    column matches the rank shown in the table when ties form or split.
    """
    stored_ranks = snapshot.get("ranks", {})
    if stored_ranks:
        return stored_ranks

    snapshot_contributions = snapshot.get("contributions", {})
    if any(
        current_year_label in year_data for year_data in snapshot_contributions.values()
    ):
        snapshot_rows = []
        for username, year_data in snapshot_contributions.items():
            row = {"username": username}
            row.update(year_data)
            snapshot_rows.append(row)
        ranks, _ = _compute_rank_metadata(snapshot_rows, current_year_label)
        return ranks

    return snapshot.get("positions", {})


def _movement_delta(previous_rank, current_rank):
    """Return rank movement using the visible competition ranks."""
    return previous_rank - current_rank


def _backup_config(path: Path):
    """Create a backup of the config file, with timestamping if .bak exists."""
    backup = path.with_suffix(path.suffix + ".bak")
    if backup.exists():
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup = path.with_suffix(f"{path.suffix}.{timestamp}.bak")
    shutil.copy(path, backup)
    return backup


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--config", default=None, help="Path to config file.")
@click.option(
    "--users",
    default=None,
    help="Comma-separated list of GitHub usernames to surveil.",
)
@click.option(
    "--team",
    default=None,
    help="Surveil a named team from config (see [teams.*] in config file).",
)
@click.option(
    "--years",
    default=None,
    type=int,
    help="Number of prior years to include (in addition to current year).",
)
@click.option(
    "--period",
    default=None,
    type=click.Choice(list(VALID_PERIODS), case_sensitive=False),
    help="Report on a named window: week, month, or year. Overrides --years.",
)
@click.option(
    "--last-months",
    default=None,
    type=int,
    help="Show the last N calendar months as separate columns.",
)
@click.option(
    "--last-weeks",
    default=None,
    type=int,
    help="Show the last N ISO weeks as separate columns.",
)
@click.option(
    "--since",
    default=None,
    metavar="DATE",
    help="Start of a custom date range (YYYY-MM-DD). End defaults to today.",
)
@click.option(
    "--until",
    default=None,
    metavar="DATE",
    help="End of a custom date range (YYYY-MM-DD). Requires --since.",
)
@click.option(
    "--show-config",
    is_flag=True,
    default=False,
    help="Print the current configuration and exit.",
)
@click.option(
    "--init-config",
    is_flag=True,
    default=False,
    help="Write a default config file and exit.",
)
@click.option(
    "--update-config",
    is_flag=True,
    default=False,
    help="Add missing keys from template to existing config and exit.",
)
@click.option(
    "--export-config",
    "export_config",
    is_flag=True,
    default=False,
    help="Print a TOML config scaffolded from current CLI arguments and exit.",
)
@click.option(
    "--github-url",
    default=None,
    help="GitHub base URL (default: https://github.com). For GitHub Enterprise Server.",
)
@click.option(
    "--no-update-check",
    is_flag=True,
    default=False,
    # No envvar= here: Click would route GH_SNITCH_NO_UPDATE_CHECK through its
    # BOOL converter, so unrecognised values abort the run. Resolved by
    # presence in the callback instead — see _env_flag_is_set.
    help=(
        "Skip checking for updates."
        " Also honoured via the GH_SNITCH_NO_UPDATE_CHECK environment"
        " variable, set to any non-empty value."
    ),
)
@click.option(
    "--api-stats",
    is_flag=True,
    default=False,
    help=(
        "Print GraphQL request counts and rate-limit diagnostics to stderr "
        "after output."
    ),
)
@click.option(
    "--no-trend",
    is_flag=True,
    default=False,
    help="Hide the Trend column.",
)
@click.option(
    "--min-contributions",
    default=None,
    type=int,
    help="Hide operatives with fewer than N contributions in the current year.",
)
@click.option(
    "--totals",
    is_flag=True,
    default=False,
    help="Show a Total column per operative and a Total footer row.",
)
@click.option(
    "--percent",
    is_flag=True,
    default=False,
    help="Annotate each cell with the operative's (N%) share of that year's total.",
)
@click.option(
    "--no-rank-delta",
    is_flag=True,
    default=False,
    help="Hide the ± column showing rank change since the last run.",
)
@click.option(
    "--redact",
    is_flag=True,
    default=False,
    help="Replace operative usernames with NATO codenames for shareable output.",
)
@click.option(
    "--delta",
    is_flag=True,
    default=False,
    help="Show change since the last snapshot instead of the current-year count.",
)
@click.option(
    "--reset-snapshot",
    is_flag=True,
    default=False,
    help="Clear the saved contribution snapshot and exit.",
)
@click.option(
    "--format",
    "output_format",
    default=None,
    type=click.Choice(list(VALID_FORMATS), case_sensitive=False),
    help="Output format: table (default), json, csv, markdown, or graph.",
)
@click.version_option(version=importlib.metadata.version("ghsnitch"))
def gh_snitch(  # noqa: PLR0913
    ctx,
    config,
    users,
    team,
    years,
    period,
    last_months,
    last_weeks,
    since,
    until,
    github_url,
    show_config,
    init_config,
    update_config,
    export_config,
    no_update_check,
    api_stats,
    no_trend,
    min_contributions,
    totals,
    percent,
    no_rank_delta,
    redact,
    delta,
    reset_snapshot,
    output_format,
):
    """Spy-themed GitHub contribution surveillance tool."""
    # This callback body *is* the program — without this guard, `gh-snitch
    # completions bash` would query GitHub's GraphQL API before dispatching.
    # Subcommands must also stay usable with no config file and no token, so
    # return before any of the setup and validation below.
    if ctx.invoked_subcommand is not None:
        return

    run_start = time.monotonic()
    configure_api_stats(api_stats)
    setup_logging()
    logger.info(
        "gh-snitch started config=%s users=%s years=%s period=%s "
        "last_months=%s last_weeks=%s since=%s until=%s github_url=%s",
        config,
        users,
        years,
        period,
        last_months,
        last_weeks,
        since,
        until,
        github_url,
    )

    if init_config:
        path = Path(config) if config else get_config_path()
        overwrite = path.exists()
        if overwrite:
            click.confirm(
                f"🚨 Operative config already exists at {path}. Overwrite and backup?",
                abort=True,
            )
            backup = _backup_config(path)
            click.echo(f"📦 Original dossier secured at: {backup}", err=True)

        path = generate_default_config(config, overwrite=overwrite)
        click.echo(f"🗂️  Handler config established at: {path}", err=True)
        return

    if update_config:
        path = Path(config) if config else get_config_path()
        if not path.exists():
            click.echo(
                f"🚨 No config file found at {path} to update. "
                "Run with --init-config to create one.",
                err=True,
            )
            sys.exit(1)

        backup = _backup_config(path)
        click.echo(f"🗂️  Backed up current dossier to {backup}", err=True)

        added = config_module.update_config(config)
        if added:
            click.echo(f"✅  Added {len(added)} new keys to your config:", err=True)
            for key in sorted(added):
                click.echo(f"    {key}", err=True)
        else:
            click.echo("✅  Config is already up to date.", err=True)
        return

    cfg = load_config(config)

    # Any one of the flag, the environment variable, or the config key
    # switching the check off is enough; none of them can switch it back on.
    no_update_check = (
        no_update_check
        or _env_flag_is_set("GH_SNITCH_NO_UPDATE_CHECK")
        or cfg.get("no_update_check", False)
    )

    if show_config:
        click.echo(f"users = {cfg['users']}")
        click.echo(f"years = {cfg['years']}")
        click.echo(f"period = {cfg['period']}")
        click.echo(f"last_months = {cfg['last_months']}")
        click.echo(f"last_weeks = {cfg['last_weeks']}")
        click.echo(f"output_format = {cfg.get('output_format', 'table')}")
        click.echo(f"github_url = {cfg['github_url']}")
        # The resolved value, not the raw config key: --show-config should say
        # what will actually happen, flag and environment variable included.
        click.echo(f"no-update-check = {no_update_check}")
        teams = cfg.get("teams", {})
        if teams:
            for team_name, members in sorted(teams.items()):
                click.echo(f"teams.{team_name} = {members}")
        else:
            click.echo("teams = {}")
        return

    # Validate --since / --until before touching config.
    if until is not None and since is None:
        click.echo("⚠️  --until requires --since to be set.", err=True)
        sys.exit(1)

    # Merge CLI overrides
    if users is not None:
        cfg["users"] = [u.strip() for u in users.split(",") if u.strip()]
    elif team is not None:
        teams = cfg.get("teams", {})
        if team not in teams:
            available = ", ".join(sorted(teams.keys())) or "none"
            click.echo(
                f"🚨 Team '{team}' not found in config. Known cells: {available}.",
                err=True,
            )
            sys.exit(1)
        cfg["users"] = teams[team]

    operative_list = cfg["users"]

    # Build redact map: sorted usernames → NATO codenames (deterministic).
    redact_map: dict[str, str] = {}
    if redact:
        for i, username in enumerate(sorted(operative_list)):
            suffix = f"-{i // 26 + 1}" if i >= 26 else ""
            redact_map[username] = f"Operative {_NATO_ALPHABET[i % 26]}{suffix}"

    # Calculate context ID for partitioned snapshot caching.
    context_id = None
    if team:
        context_id = f"team-{team}"
    elif operative_list:
        # For ad-hoc user lists, use a hash of the sorted members.
        user_key = ",".join(sorted(operative_list))
        user_hash = hashlib.sha256(user_key.encode()).hexdigest()[:12]
        context_id = f"u-{user_hash}"

    if years is not None:
        cfg["years"] = years
    if period is not None:
        cfg["period"] = period.lower()
    if last_months is not None:
        cfg["last_months"] = last_months
    if last_weeks is not None:
        cfg["last_weeks"] = last_weeks
    if github_url is not None:
        cfg["github_url"] = github_url
    if min_contributions is not None:
        cfg["min_contributions"] = min_contributions
    if totals:
        cfg["totals"] = True
    if percent:
        cfg["percent"] = True
    if no_rank_delta:
        cfg["rank_delta"] = False
    if output_format is not None:
        cfg["output_format"] = output_format.lower()

    if export_config:
        click.echo(config_module.render_config(cfg))
        return

    if reset_snapshot:
        clear_all_snapshots()
        click.echo("🗑️  All snapshots cleared. Operative history wiped.", err=True)
        return

    if not SECRET_GITHUB_TOKEN:
        click.echo(
            "🚨 GH_TOKEN or GITHUB_TOKEN not set. "
            "Operatives cannot be surveilled without credentials.",
            err=True,
        )
        sys.exit(1)

    active_format = cfg.get("output_format", "table")

    num_years = cfg["years"]
    active_period = cfg.get("period")
    active_last_months = cfg.get("last_months")
    active_last_weeks = cfg.get("last_weeks")
    operative_github_url = cfg["github_url"]

    # Scope snapshots by the resolved user cohort + GitHub instance so rank
    # movement only compares against the same group of operatives.
    snapshot_scope = compute_scope(operative_list, operative_github_url)

    logger.info(
        "effective config operatives=%s years=%s period=%s "
        "last_months=%s last_weeks=%s github_url=%s",
        operative_list,
        num_years,
        active_period,
        active_last_months,
        active_last_weeks,
        operative_github_url,
    )

    if not operative_list:
        click.echo(
            "⚠️  No operatives configured. Add users to your config or use --users.",
            err=True,
        )
        return

    # Resolve the active date ranges (highest-precedence wins).
    # suppress_trend: True when the columns are not comparable year-over-year.
    suppress_trend = False
    if since is not None:
        try:
            active_year_ranges = [get_custom_range(since, until)]
        except ValueError as e:
            click.echo(f"⚠️  {e}", err=True)
            sys.exit(1)
        suppress_trend = True
    elif active_last_months is not None:
        active_year_ranges = get_rolling_month_ranges(active_last_months)
        suppress_trend = True
    elif active_last_weeks is not None:
        active_year_ranges = get_rolling_week_ranges(active_last_weeks)
        suppress_trend = True
    elif active_period is not None:
        active_year_ranges = [get_period_range(active_period)]
        # trend suppressed implicitly by len < 2 in render_table
    else:
        active_year_ranges = get_year_ranges(num_years)

    click.echo("🔍 Initiating surveillance sweep...", err=True)

    num_ranges = len(active_year_ranges)
    use_progress = sys.stderr.isatty()

    progress = Progress(
        TextColumn("[bold blue]📡 Sweeping field reports..."),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[dim]{task.completed}/{task.total} ranges"),
        console=Console(stderr=True),
        disable=not use_progress,
    )

    logger.info(
        "sweep starting operatives=%s num_ranges=%d",
        operative_list,
        num_ranges,
    )
    sweep_start = time.monotonic()
    try:
        with progress:
            task = progress.add_task("sweep", total=num_ranges)

            def on_progress(completed, total):  # noqa: ARG001
                progress.update(task, completed=completed)

            data, not_found = fetch_contributions(
                operative_list,
                num_years,
                operative_github_url,
                on_progress,
                year_ranges=active_year_ranges,
            )
    except GitHubGraphQLRateLimitError as e:
        duration = time.monotonic() - sweep_start
        logger.error(
            "sweep failed after %.3fs: rate_limited error_count=%d errors=%s reset=%s",
            duration,
            e.error_count,
            e.summary,
            e.reset_at,
        )
        if e.reset_at:
            click.echo(
                "⏱️  Surveillance rate limit reached. "
                f"GitHub signals reset at {e.reset_at}. "
                "Stand down and retry after that time.",
                err=True,
            )
        else:
            click.echo(
                "⏱️  Surveillance rate limit reached. "
                "Stand down briefly and try again.",
                err=True,
            )
        sys.exit(1)
    except GitHubGraphQLResourceLimitError as e:
        duration = time.monotonic() - sweep_start
        logger.error(
            "sweep failed after %.3fs: resource_limited error_count=%d errors=%s",
            duration,
            e.error_count,
            e.summary,
        )
        click.echo(
            "🕵️  Surveillance query exceeded GitHub's resource limits. "
            "Reduce the number of operatives or time ranges and try again.",
            err=True,
        )
        sys.exit(1)
    except GitHubGraphQLError as e:
        duration = time.monotonic() - sweep_start
        logger.error(
            "sweep failed after %.3fs: graphql_error error_count=%d errors=%s",
            duration,
            e.error_count,
            e.summary,
        )
        click.echo(f"🕵️  Surveillance query failed: {e.summary}", err=True)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        duration = time.monotonic() - sweep_start
        detail = _bounded_error_detail(e)
        logger.error("sweep failed after %.3fs: network_error=%s", duration, detail)
        click.echo(
            f"📡 Signal lost after retries. Operative unreachable: {detail}",
            err=True,
        )
        sys.exit(1)

    duration = time.monotonic() - sweep_start
    logger.info("sweep complete duration=%.3fs", duration)

    year_labels = [label for label, _, _ in active_year_ranges]

    rows = []
    for username, year_data in data.items():
        row = {"username": username}
        row.update(year_data)
        rows.append(row)

    # Load the previous snapshot before potentially overwriting it.
    # Snapshot is only saved on non-delta runs so the baseline stays pinned;
    # repeated --delta invocations compare against the same fixed point.
    prev_snapshot = load_snapshot(scope=snapshot_scope, context_id=context_id)

    # Compute current rank metadata using the same sort order as render_table.
    current_year_label = year_labels[0]
    current_ranks, current_positions = _compute_rank_metadata(rows, current_year_label)

    if not delta:
        save_snapshot(
            {
                row["username"]: {lbl: row.get(lbl, 0) for lbl in year_labels}
                for row in rows
            },
            ranks=current_ranks,
            positions=current_positions,
            scope=snapshot_scope,
            context_id=context_id,
        )

    # Compute visible leaderboard movement from displayed competition ranks.
    rank_deltas = None
    if prev_snapshot is not None:
        prev_ranks = _get_snapshot_ranks(prev_snapshot, current_year_label)
        if prev_ranks:
            rank_deltas = {}
            for username, curr_position in current_positions.items():
                if username not in prev_ranks:
                    rank_deltas[username] = None  # new operative
                else:
                    rank_deltas[username] = _movement_delta(
                        prev_ranks[username], curr_position
                    )

    threshold = cfg["min_contributions"]
    suppressed = 0
    if threshold > 0 and year_labels:
        current_year_label = year_labels[0]
        filtered_rows = []
        for row in rows:
            if row.get(current_year_label, 0) >= threshold:
                filtered_rows.append(row)
            else:
                suppressed += 1
        rows = filtered_rows

    # Detect ghost operatives: zero contributions across every surveilled window.
    ghost_usernames = {
        row["username"]
        for row in rows
        if all(row.get(lbl, 0) == 0 for lbl in year_labels)
    }

    # Apply delta transformation if requested.
    delta_col = None
    if delta:
        current_label = year_labels[0]
        if prev_snapshot is None:
            click.echo(
                "📸 No prior snapshot found — showing absolute counts. "
                "Run again with --delta to see changes.",
                err=True,
            )
        else:
            prev_data = prev_snapshot.get("contributions", {})
            for row in rows:
                username = row["username"]
                prev_count = prev_data.get(username, {}).get(current_label, 0)
                row[current_label] = row.get(current_label, 0) - prev_count
            year_labels = ["Δ Today"]
            # Rename key in each row so render_table can look it up
            for row in rows:
                row["Δ Today"] = row.pop(current_label)
            delta_col = "Δ Today"
            # Rank deltas are not meaningful when showing contribution deltas
            rank_deltas = None

    show_totals = cfg.get("totals", False)

    _redact = redact_map or None
    if active_format == "json":
        click.echo(
            render_json(rows, year_labels, show_totals=show_totals, redact_map=_redact)
        )
    elif active_format == "csv":
        click.echo(
            render_csv(rows, year_labels, show_totals=show_totals, redact_map=_redact),
            nl=False,
        )
    elif active_format == "markdown":
        click.echo(
            render_markdown(
                rows, year_labels, show_totals=show_totals, redact_map=_redact
            )
        )
    elif active_format == "graph":
        if cfg.get("percent"):
            click.echo(
                "⚠️  --percent is ignored in graph format.",
                err=True,
            )
        if show_totals:
            click.echo(
                "⚠️  --totals is ignored in graph format (no footer rows in charts).",
                err=True,
            )
        click.echo(
            render_graph(rows, year_labels, show_totals=show_totals, redact_map=_redact)
        )
    elif active_format == "stack":
        if cfg.get("percent"):
            click.echo("⚠️  --percent is ignored in stack format.", err=True)
        if show_totals:
            click.echo("⚠️  --totals is ignored in stack format.", err=True)
        click.echo(render_stack(rows, year_labels, redact_map=_redact))
    else:
        table = render_table(
            rows,
            year_labels,
            year_fraction=current_year_fraction(),
            show_trend=not no_trend and delta_col is None and not suppress_trend,
            show_totals=show_totals,
            show_percent=cfg.get("percent", False),
            show_rank_delta=cfg.get("rank_delta", True),
            delta_col=delta_col,
            rank_deltas=rank_deltas,
            ghost_usernames=ghost_usernames if not delta else None,
            redact_map=_redact,
            github_url=operative_github_url,
        )
        click.echo(table)

    if suppressed > 0:
        click.echo(
            f"🔕 {suppressed} operative(s) below threshold suppressed.",
            err=True,
        )

    if ghost_usernames:
        click.echo(
            f"👻 {len(ghost_usernames)} ghost operative(s) detected — "
            "zero activity across all surveilled windows.",
            err=True,
        )

    if not_found:
        for username in sorted(not_found):
            display = redact_map.get(username, username) if redact_map else username
            click.echo(
                f"⚠️  Operative '{display}' not found — they may have gone dark.",
                err=True,
            )
        click.echo(
            f"🚨 {len(not_found)} operative(s) could not be located. "
            "Verify their handles and try again.",
            err=True,
        )

    click.echo(
        "🗂️  Dossier compiled. Handler review recommended.",
        err=True,
    )

    if not no_update_check:
        update_msg = check_for_update()
        if update_msg:
            click.echo(update_msg, err=True)

    if api_stats:
        stats = get_api_stats()
        rate_limit = get_graphql_rate_limit(operative_github_url)
        _print_api_stats_summary(
            run_start,
            len(operative_list),
            stats,
            rate_limit,
        )

    if not_found:
        sys.exit(1)


# ── Shell completions ───────────────────────────────────────────────────────


@gh_snitch.command()
@click.argument("shell", type=click.Choice(_SHELL_CHOICES))
def completions(shell):
    """Print the shell completion script for SHELL.

    Eval it in your shell config, e.g. ``eval "$(gh-snitch completions bash)"``.
    """
    from click.shell_completion import get_completion_class

    comp_cls = get_completion_class(Shell(shell))
    comp = comp_cls(
        cli=gh_snitch,
        ctx_args={},
        prog_name="gh-snitch",
        complete_var="_GH_SNITCH_COMPLETE",
    )
    click.echo(comp.source(), nl=False)


# ── Self-update ─────────────────────────────────────────────────────────────


def _current_executable_path() -> str:
    """Resolve the absolute path of the running gh-snitch executable.

    ``sys.argv[0]`` is what the user actually invoked, so prefer it whenever it
    names a real file: ``./gh-snitch update`` must update *that* copy, not a
    different one that happens to sit earlier on PATH. Fall back to a PATH
    lookup for the usual case, where argv[0] is the bare console-script name.

    ``abspath`` rather than ``resolve`` so a symlinked install has its link
    replaced and not the file it points at, and so a relative argv[0] cannot
    send ``os.replace()`` to the current working directory.
    """
    invoked = sys.argv[0]
    if os.sep in invoked and os.path.isfile(invoked):
        return os.path.abspath(invoked)
    return os.path.abspath(shutil.which("gh-snitch") or invoked)


@gh_snitch.command()
def update():
    """Requisition the latest gh-snitch release over this executable."""
    click.echo(
        click.style("🕵️ Checking for a fresher intelligence package...", fg="cyan"),
        err=True,
    )
    status, current, detail = perform_update(_current_executable_path())

    if status is UpdateStatus.UNKNOWN:
        raise click.ClickException("Could not reach GitHub to check for a new release.")
    if status is UpdateStatus.ERROR:
        raise click.ClickException(f"Update failed: {detail}")
    if status is UpdateStatus.UP_TO_DATE:
        click.echo(
            click.style(
                f"📡 Operative already running the latest package, v{current}.",
                fg="green",
            ),
            err=True,
        )
        return

    click.echo(
        click.style(f"📡 Operative upgraded to v{detail}.", fg="green"), err=True
    )
    # The completion scripts re-invoke the binary, so they track it for free.
    # The man page is a static file and may sit somewhere needing privileges,
    # so point at the installer rather than trying to rewrite it here.
    click.echo(
        click.style(
            "   Re-run install.sh if you also want a refreshed man page.", fg="cyan"
        ),
        err=True,
    )
