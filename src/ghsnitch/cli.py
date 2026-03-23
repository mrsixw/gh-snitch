import importlib.metadata
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
from .logger import log_run
from .ui import render_table
from .updater import check_for_update


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
):
    """Spy-themed GitHub contribution surveillance tool."""
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

    operative_list = cfg["users"]
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

    sweep_start = time.monotonic()
    try:
        with progress:
            task = progress.add_task("sweep", total=num_years_total)

            def on_progress(completed, total):  # noqa: ARG001
                progress.update(task, completed=completed)

            data = fetch_contributions(
                operative_list, num_years, operative_github_url, on_progress
            )
    except requests.exceptions.RequestException as e:
        duration = time.monotonic() - sweep_start
        log_run(operative_list, [], {}, duration, error=str(e))
        click.echo(f"📡 Signal lost. Operative unreachable: {e}", err=True)
        sys.exit(1)

    duration = time.monotonic() - sweep_start

    year_ranges = get_year_ranges(num_years)
    year_labels = [label for label, _, _ in year_ranges]

    rows = []
    for username, year_data in data.items():
        row = {"username": username}
        row.update(year_data)
        rows.append(row)

    log_run(operative_list, year_labels, data, duration)

    table = render_table(
        rows,
        year_labels,
        year_fraction=current_year_fraction(),
        show_trend=not no_trend,
    )
    click.echo(table)
    click.echo("🗂️  Dossier compiled. Handler review recommended.")

    if not no_update_check:
        update_msg = check_for_update()
        if update_msg:
            click.echo(update_msg)
