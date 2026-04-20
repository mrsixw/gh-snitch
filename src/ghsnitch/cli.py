import importlib.metadata
import logging
import math
import sys
import time

import click
import requests
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

from .api import (
    SECRET_GITHUB_TOKEN,
    VALID_PERIODS,
    current_year_fraction,
    fetch_contributions,
    get_custom_range,
    get_period_range,
    get_rolling_month_ranges,
    get_rolling_week_ranges,
    get_year_ranges,
)
from .config import generate_default_config, load_config
from .logger import setup_logging
from .snapshot import clear_snapshot, load_snapshot, save_snapshot
from .ui import render_csv, render_json, render_markdown, render_table
from .updater import check_for_update

VALID_FORMATS = ("table", "json", "csv", "markdown")

logger = logging.getLogger(__name__)


def _compute_rank_metadata(rows, current_year_label):
    """Return display ranks and tie-aware movement positions for the leaderboard.

    Args:
        rows: iterable of contribution rows with a ``username`` key
        current_year_label: year label used to sort the leaderboard

    Returns:
        tuple[dict[str, int], dict[str, float]]: competition ranks for display
        and average occupied positions for movement tracking
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
        average_position = (competition_rank + group_end) / 2
        for row in sorted_rows[i:group_end]:
            username = row["username"]
            ranks[username] = competition_rank
            positions[username] = average_position

        i = group_end
    return ranks, positions


def _get_snapshot_positions(snapshot, current_year_label):
    """Return tie-aware movement positions for a previous snapshot if possible.

    Newer snapshots persist explicit movement positions. Older snapshots can
    still be upgraded in place by deriving tie-aware positions from their
    contribution
    counts for the current year. If that data is unavailable, fall back to the
    legacy rank metadata so movement continues to work across year boundaries.
    """
    stored_positions = snapshot.get("positions", {})
    if stored_positions:
        return stored_positions

    snapshot_contributions = snapshot.get("contributions", {})
    if any(
        current_year_label in year_data for year_data in snapshot_contributions.values()
    ):
        snapshot_rows = []
        for username, year_data in snapshot_contributions.items():
            row = {"username": username}
            row.update(year_data)
            snapshot_rows.append(row)
        _, positions = _compute_rank_metadata(snapshot_rows, current_year_label)
        return positions

    return snapshot.get("ranks", {})


def _movement_delta(previous_position, current_position):
    """Return an integer movement delta from tie-aware position scores."""
    raw_delta = previous_position - current_position
    if raw_delta == 0:
        return 0
    return int(math.copysign(math.ceil(abs(raw_delta)), raw_delta))


@click.command()
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
    "--github-url",
    default=None,
    help="GitHub base URL (default: https://github.com). For GitHub Enterprise Server.",
)
@click.option(
    "--no-update-check",
    is_flag=True,
    default=False,
    help="Skip checking for updates.",
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
    help="Output format: table (default), json, csv, or markdown.",
)
@click.version_option(version=importlib.metadata.version("ghsnitch"))
def gh_snitch(  # noqa: PLR0913
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
    no_update_check,
    no_trend,
    min_contributions,
    totals,
    percent,
    delta,
    reset_snapshot,
    output_format,
):
    """Spy-themed GitHub contribution surveillance tool."""
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

    if reset_snapshot:
        clear_snapshot()
        click.echo("🗑️  Snapshot cleared. Operative history wiped.", err=True)
        return

    if init_config:
        path = generate_default_config(config)
        click.echo(f"🗂️  Handler config established at: {path}", err=True)
        return

    if show_config:
        cfg = load_config(config)
        click.echo(f"users = {cfg['users']}")
        click.echo(f"years = {cfg['years']}")
        click.echo(f"period = {cfg['period']}")
        click.echo(f"last_months = {cfg['last_months']}")
        click.echo(f"last_weeks = {cfg['last_weeks']}")
        click.echo(f"output_format = {cfg.get('output_format', 'table')}")
        click.echo(f"github_url = {cfg['github_url']}")
        teams = cfg.get("teams", {})
        if teams:
            for team_name, members in sorted(teams.items()):
                click.echo(f"teams.{team_name} = {members}")
        else:
            click.echo("teams = {}")
        return

    if not SECRET_GITHUB_TOKEN:
        click.echo(
            "🚨 GITHUB_TOKEN not set. "
            "Operatives cannot be surveilled without credentials.",
            err=True,
        )
        sys.exit(1)

    cfg = load_config(config)

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
    if output_format is not None:
        cfg["output_format"] = output_format.lower()

    active_format = cfg.get("output_format", "table")

    operative_list = cfg["users"]
    num_years = cfg["years"]
    active_period = cfg.get("period")
    active_last_months = cfg.get("last_months")
    active_last_weeks = cfg.get("last_weeks")
    operative_github_url = cfg["github_url"]

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
    except requests.exceptions.RequestException as e:
        duration = time.monotonic() - sweep_start
        logger.error("sweep failed after %.3fs: %s", duration, e)
        click.echo(f"📡 Signal lost. Operative unreachable: {e}", err=True)
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
    prev_snapshot = load_snapshot()

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
        )

    # Compute visible leaderboard movement from tie-aware position scores.
    rank_deltas = None
    if prev_snapshot is not None:
        prev_positions = _get_snapshot_positions(prev_snapshot, current_year_label)
        if prev_positions:
            rank_deltas = {}
            for username, curr_position in current_positions.items():
                if username not in prev_positions:
                    rank_deltas[username] = None  # new operative
                else:
                    rank_deltas[username] = _movement_delta(
                        prev_positions[username], curr_position
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

    if active_format == "json":
        click.echo(render_json(rows, year_labels, show_totals=show_totals))
    elif active_format == "csv":
        click.echo(render_csv(rows, year_labels, show_totals=show_totals), nl=False)
    elif active_format == "markdown":
        click.echo(render_markdown(rows, year_labels, show_totals=show_totals))
    else:
        table = render_table(
            rows,
            year_labels,
            year_fraction=current_year_fraction(),
            show_trend=not no_trend and delta_col is None and not suppress_trend,
            show_totals=show_totals,
            show_percent=cfg.get("percent", False),
            delta_col=delta_col,
            rank_deltas=rank_deltas,
        )
        click.echo(table)

    if suppressed > 0:
        click.echo(
            f"🔕 {suppressed} operative(s) below threshold suppressed.",
            err=True,
        )

    if not_found:
        for username in sorted(not_found):
            click.echo(
                f"⚠️  Operative '{username}' not found — they may have gone dark.",
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

    if not_found:
        sys.exit(1)
