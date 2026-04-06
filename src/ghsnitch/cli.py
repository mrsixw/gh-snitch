import importlib.metadata
import logging
import sys
import time

import click
import requests
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

from .api import (
    SECRET_GITHUB_TOKEN,
    current_year_fraction,
    fetch_contributions,
    get_year_ranges,
)
from .config import generate_default_config, load_config
from .logger import setup_logging
from .snapshot import clear_snapshot, load_snapshot, save_snapshot
from .ui import render_table
from .updater import check_for_update

logger = logging.getLogger(__name__)


@click.command()
@click.option("--config", default=None, help="Path to config file.")
@click.option(
    "--users",
    default=None,
    help="Comma-separated list of GitHub usernames to surveil.",
)
@click.option(
    "--years",
    default=None,
    type=int,
    help="Number of prior years to include (in addition to current year).",
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
@click.version_option(version=importlib.metadata.version("ghsnitch"))
def gh_snitch(  # noqa: PLR0913
    config,
    users,
    years,
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
):
    """Spy-themed GitHub contribution surveillance tool."""
    setup_logging()
    logger.info(
        "gh-snitch started config=%s users=%s years=%s github_url=%s",
        config,
        users,
        years,
        github_url,
    )

    if reset_snapshot:
        clear_snapshot()
        click.echo("🗑️  Snapshot cleared. Operative history wiped.")
        return

    if init_config:
        path = generate_default_config(config)
        click.echo(f"🗂️  Handler config established at: {path}")
        return

    if show_config:
        cfg = load_config(config)
        click.echo(f"users = {cfg['users']}")
        click.echo(f"years = {cfg['years']}")
        click.echo(f"github_url = {cfg['github_url']}")
        return

    if not SECRET_GITHUB_TOKEN:
        click.echo(
            "🚨 GITHUB_TOKEN not set. "
            "Operatives cannot be surveilled without credentials.",
            err=True,
        )
        sys.exit(1)

    cfg = load_config(config)

    # Merge CLI overrides
    if users is not None:
        cfg["users"] = [u.strip() for u in users.split(",") if u.strip()]
    if years is not None:
        cfg["years"] = years
    if github_url is not None:
        cfg["github_url"] = github_url
    if min_contributions is not None:
        cfg["min_contributions"] = min_contributions
    if totals:
        cfg["totals"] = True
    if percent:
        cfg["percent"] = True

    operative_list = cfg["users"]
    logger.info(
        "effective config operatives=%s years=%s github_url=%s",
        operative_list,
        cfg["years"],
        cfg["github_url"],
    )
    num_years = cfg["years"]
    operative_github_url = cfg["github_url"]

    if not operative_list:
        click.echo(
            "⚠️  No operatives configured. Add users to your config or use --users.",
            err=True,
        )
        return

    click.echo("🔍 Initiating surveillance sweep...")

    num_years_total = num_years + 1  # current year + prior years
    use_progress = sys.stdout.isatty()

    progress = Progress(
        TextColumn("[bold blue]📡 Sweeping field reports..."),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[dim]{task.completed}/{task.total} years"),
        disable=not use_progress,
    )

    logger.info("sweep starting operatives=%s num_years=%d", operative_list, num_years)
    sweep_start = time.monotonic()
    try:
        with progress:
            task = progress.add_task("sweep", total=num_years_total)

            def on_progress(completed, total):  # noqa: ARG001
                progress.update(task, completed=completed)

            data, not_found = fetch_contributions(
                operative_list, num_years, operative_github_url, on_progress
            )
    except requests.exceptions.RequestException as e:
        duration = time.monotonic() - sweep_start
        logger.error("sweep failed after %.3fs: %s", duration, e)
        click.echo(f"📡 Signal lost. Operative unreachable: {e}", err=True)
        sys.exit(1)

    duration = time.monotonic() - sweep_start
    logger.info("sweep complete duration=%.3fs", duration)

    year_ranges = get_year_ranges(num_years)
    year_labels = [label for label, _, _ in year_ranges]

    rows = []
    for username, year_data in data.items():
        row = {"username": username}
        row.update(year_data)
        rows.append(row)

    # Always persist a snapshot so --delta and rank-delta work on the next run.
    # Load the previous snapshot first (before overwriting it).
    prev_snapshot = load_snapshot()

    # Compute current ranks (competition ranking, same sort order as render_table).
    current_year_label = year_labels[0]
    sorted_for_ranks = sorted(
        rows, key=lambda r: (-r.get(current_year_label, 0), r["username"])
    )
    current_ranks: dict[str, int] = {}
    for i, row in enumerate(sorted_for_ranks):
        if i == 0:
            current_ranks[row["username"]] = 1
        else:
            prev_count = sorted_for_ranks[i - 1].get(current_year_label, 0)
            curr_count = row.get(current_year_label, 0)
            prev_rank = current_ranks[sorted_for_ranks[i - 1]["username"]]
            current_ranks[row["username"]] = (
                prev_rank if curr_count == prev_count else i + 1
            )

    save_snapshot(
        {
            row["username"]: {lbl: row.get(lbl, 0) for lbl in year_labels}
            for row in rows
        },
        ranks=current_ranks,
    )

    # Compute rank deltas if a previous run's ranks are available.
    rank_deltas = None
    if prev_snapshot is not None:
        prev_ranks: dict[str, int] = prev_snapshot.get("ranks", {})
        if prev_ranks:
            rank_deltas = {}
            for username, curr_rank in current_ranks.items():
                if username not in prev_ranks:
                    rank_deltas[username] = None  # new operative
                else:
                    rank_deltas[username] = prev_ranks[username] - curr_rank

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

    table = render_table(
        rows,
        year_labels,
        year_fraction=current_year_fraction(),
        show_trend=not no_trend and delta_col is None,
        show_totals=cfg.get("totals", False),
        show_percent=cfg.get("percent", False),
        delta_col=delta_col,
        rank_deltas=rank_deltas,
    )
    click.echo(table)

    if suppressed > 0:
        click.echo(f"🔕 {suppressed} operative(s) below threshold suppressed.")

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

    click.echo("🗂️  Dossier compiled. Handler review recommended.")

    if not no_update_check:
        update_msg = check_for_update()
        if update_msg:
            click.echo(update_msg)

    if not_found:
        sys.exit(1)
