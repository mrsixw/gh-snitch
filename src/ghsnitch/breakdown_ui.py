"""Terminal renderers for GitHub contribution category breakdowns."""

import io
import os

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text
from tabulate import tabulate

from . import ui
from .breakdown import (
    VALID_BREAKDOWN_STYLES,
    ContributionBreakdown,
    has_other_contributions,
    sum_breakdowns,
)

__all__ = [
    "render_breakdown_table",
]


def _breakdown_for(breakdowns, username, label, fallback_total=0):
    """Return the ContributionBreakdown for (username, label)."""
    if breakdowns is not None:
        item = breakdowns.get(username, {}).get(label)
        if item is not None:
            return item
    return ContributionBreakdown(total=fallback_total)


def _format_pct(part, whole):
    """Return an integer percentage annotation ``(N%)``."""
    pct = (part / whole * 100) if whole > 0 else 0.0
    return f"({pct:.0f}%)"


def _dim(text):
    """Return dim ANSI-styled text in TTY mode, plain text otherwise."""
    if ui.IS_TTY:
        return f"\033[2m{text}\033[0m"
    return str(text)


def _format_headline_cell(
    count,
    username,
    col_values,
    period_total,
    *,
    show_percent,
    redact_map,
    github_url,
):
    """Format an operative's headline period count with optional colour/link/%."""
    if redact_map is not None:
        if ui.IS_TTY:
            prefix, suffix = ui.grade_colour(count, col_values)
            cell = f"{prefix}{count}{suffix}"
        else:
            cell = str(count)
    else:
        contrib_url = f"{github_url.rstrip('/')}/{username}"
        cell = ui.make_coloured_hyperlink_cell(count, contrib_url, col_values)

    if show_percent:
        pct_annotation = _format_pct(count, period_total)
        cell = f"{cell} {_dim(pct_annotation)}"
    return cell


def _format_category_value(value, operative_total, *, show_percent):
    """Format one category count with optional share of the operative's total."""
    text = str(value)
    if show_percent:
        text = f"{text} {_format_pct(value, operative_total)}"
    return _dim(text) if value == 0 else text


def _render_rich_to_string(renderable):
    """Render a Rich renderable to a string, honouring ``ui.IS_TTY``."""
    try:
        width = os.get_terminal_size().columns
    except OSError:
        width = 120
    buffer = io.StringIO()
    console = Console(
        file=buffer,
        force_terminal=ui.IS_TTY,
        no_color=not ui.IS_TTY,
        width=max(width, 80),
        highlight=False,
    )
    console.print(renderable, end="")
    return buffer.getvalue().rstrip("\n")


def _rich_text(value):
    """Convert a string that may contain ANSI/OSC 8 sequences into Rich Text."""
    return Text.from_ansi(str(value))


def _render_subrows(
    sorted_rows,
    ranks,
    year_labels,
    breakdowns,
    *,
    year_fraction,
    show_trend,
    show_totals,
    show_percent,
    show_rank_delta,
    rank_deltas,
    ghost_usernames,
    redact_map,
    github_url,
    include_other,
):
    """Render headline rows with tree-indented category sub-rows beneath each."""
    col_values = {
        label: [r.get(label, 0) for r in sorted_rows] for label in year_labels
    }
    year_totals = {label: sum(col_values[label]) for label in year_labels}

    headers = (
        ["#"]
        + (["±"] if show_rank_delta else [])
        + ["Operative"]
        + (["Trend"] if show_trend else [])
        + year_labels
        + (["Total"] if show_totals else [])
    )

    table_data = []
    for rank, row in zip(ranks, sorted_rows):
        username = row["username"]
        is_ghost = ghost_usernames is not None and username in ghost_usernames
        display_name = redact_map.get(username) if redact_map else None

        headline_cells = [rank]
        if show_rank_delta:
            headline_cells.append(ui.rank_delta_cell(rank_deltas.get(username)))
        headline_cells.append(
            ui.make_operative_cell(
                username,
                is_ghost=is_ghost,
                display_name=display_name,
                github_url=github_url,
            )
        )
        if show_trend:
            headline_cells.append(
                ui.trend_indicator(
                    row.get(year_labels[0], 0),
                    row.get(year_labels[1], 0),
                    year_fraction,
                )
            )

        period_items = {}
        for label in year_labels:
            count = row.get(label, 0)
            period_items[label] = _breakdown_for(breakdowns, username, label, count)
            headline_cells.append(
                _format_headline_cell(
                    count,
                    username,
                    col_values[label],
                    year_totals[label],
                    show_percent=show_percent,
                    redact_map=redact_map,
                    github_url=github_url,
                )
            )

        summed = sum_breakdowns(period_items.values())
        if show_totals:
            headline_cells.append(summed.total)
        table_data.append(headline_cells)

        categories = summed.categories(include_other=include_other)
        last_idx = len(categories) - 1
        for idx, (key, cat_label, total_val) in enumerate(categories):
            branch = "└─" if idx == last_idx else "├─"
            sub_cells = [""]
            if show_rank_delta:
                sub_cells.append("")
            sub_cells.append(_dim(f"{branch} {cat_label}"))
            if show_trend:
                sub_cells.append("")
            for label in year_labels:
                item = period_items[label]
                value = item.other if key == "other" else getattr(item, key)
                sub_cells.append(
                    _format_category_value(value, item.total, show_percent=show_percent)
                )
            if show_totals:
                sub_cells.append(
                    _format_category_value(
                        total_val, summed.total, show_percent=show_percent
                    )
                )
            table_data.append(sub_cells)

    if show_totals:
        totals_cells = [""]
        if show_rank_delta:
            totals_cells.append("")
        totals_cells.append("Total")
        if show_trend:
            totals_cells.append("")
        for label in year_labels:
            totals_cells.append(year_totals[label])
        totals_cells.append(sum(year_totals.values()))
        table_data.append(totals_cells)

    colalign = (
        ("right",)
        + (("center",) if show_rank_delta else ())
        + ("left",)
        + (("center",) if show_trend else ())
        + ("right",) * len(year_labels)
        + (("right",) if show_totals else ())
    )
    return tabulate(
        table_data,
        headers=headers,
        tablefmt="simple",
        colalign=colalign,
    )


def _mini_breakdown_table(item, headline_text, *, show_percent, include_other):
    """Build a compact inner Rich table for one cell in ``nested`` layout."""
    inner = Table(
        show_header=False,
        box=box.SIMPLE,
        pad_edge=False,
        padding=(0, 1),
        collapse_padding=True,
    )
    inner.add_column(justify="left", style="dim")
    inner.add_column(justify="right")
    inner.add_row(Text("Total", style="bold"), _rich_text(headline_text))
    for _key, cat_label, value in item.categories(include_other=include_other):
        val_text = _format_category_value(value, item.total, show_percent=show_percent)
        inner.add_row(cat_label, _rich_text(val_text))
    return inner


def _render_nested(
    sorted_rows,
    ranks,
    year_labels,
    breakdowns,
    *,
    year_fraction,
    show_trend,
    show_totals,
    show_percent,
    show_rank_delta,
    rank_deltas,
    ghost_usernames,
    redact_map,
    github_url,
    include_other,
):
    """Render a Rich table-within-table layout (mini breakdown table per cell)."""
    col_values = {
        label: [r.get(label, 0) for r in sorted_rows] for label in year_labels
    }
    year_totals = {label: sum(col_values[label]) for label in year_labels}

    outer = Table(box=box.ROUNDED if ui.IS_TTY else box.ASCII, show_lines=True)
    outer.add_column("#", justify="right")
    if show_rank_delta:
        outer.add_column("±", justify="center")
    outer.add_column("Operative", justify="left")
    if show_trend:
        outer.add_column("Trend", justify="center")
    for label in year_labels:
        outer.add_column(label, justify="right")
    if show_totals:
        outer.add_column("Total", justify="right")

    for rank, row in zip(ranks, sorted_rows):
        username = row["username"]
        is_ghost = ghost_usernames is not None and username in ghost_usernames
        display_name = redact_map.get(username) if redact_map else None

        cells = [str(rank)]
        if show_rank_delta:
            cells.append(_rich_text(ui.rank_delta_cell(rank_deltas.get(username))))
        cells.append(
            _rich_text(
                ui.make_operative_cell(
                    username,
                    is_ghost=is_ghost,
                    display_name=display_name,
                    github_url=github_url,
                )
            )
        )
        if show_trend:
            cells.append(
                _rich_text(
                    ui.trend_indicator(
                        row.get(year_labels[0], 0),
                        row.get(year_labels[1], 0),
                        year_fraction,
                    )
                )
            )

        period_items = []
        for label in year_labels:
            count = row.get(label, 0)
            item = _breakdown_for(breakdowns, username, label, count)
            period_items.append(item)
            headline = _format_headline_cell(
                count,
                username,
                col_values[label],
                year_totals[label],
                show_percent=show_percent,
                redact_map=redact_map,
                github_url=github_url,
            )
            cells.append(
                _mini_breakdown_table(
                    item,
                    headline,
                    show_percent=show_percent,
                    include_other=include_other,
                )
            )

        if show_totals:
            summed = sum_breakdowns(period_items)
            cells.append(
                _mini_breakdown_table(
                    summed,
                    str(summed.total),
                    show_percent=show_percent,
                    include_other=include_other,
                )
            )
        outer.add_row(*cells)

    if show_totals:
        footer = [""]
        if show_rank_delta:
            footer.append("")
        footer.append("Total")
        if show_trend:
            footer.append("")
        for label in year_labels:
            footer.append(str(year_totals[label]))
        footer.append(str(sum(year_totals.values())))
        outer.add_row(*footer)

    return _render_rich_to_string(outer)


def _render_cards(
    sorted_rows,
    ranks,
    year_labels,
    breakdowns,
    *,
    year_fraction,
    show_trend,
    show_totals,
    show_percent,
    show_rank_delta,
    rank_deltas,
    ghost_usernames,
    redact_map,
    github_url,
    include_other,
):
    """Render one dossier card table per operative."""
    col_values = {
        label: [r.get(label, 0) for r in sorted_rows] for label in year_labels
    }
    year_totals = {label: sum(col_values[label]) for label in year_labels}
    cards = []

    for rank, row in zip(ranks, sorted_rows):
        username = row["username"]
        is_ghost = ghost_usernames is not None and username in ghost_usernames
        display_name = redact_map.get(username) if redact_map else None
        op_cell = ui.make_operative_cell(
            username,
            is_ghost=is_ghost,
            display_name=display_name,
            github_url=github_url,
        )
        title_parts = [f"#{rank}", op_cell]
        if show_rank_delta:
            title_parts.append(f"({ui.rank_delta_cell(rank_deltas.get(username))})")
        if show_trend:
            title_parts.append(
                ui.trend_indicator(
                    row.get(year_labels[0], 0),
                    row.get(year_labels[1], 0),
                    year_fraction,
                )
            )

        card = Table(
            title=_rich_text(" ".join(title_parts)),
            title_justify="left",
            box=box.ROUNDED if ui.IS_TTY else box.ASCII,
        )
        card.add_column("Category", justify="left")
        for label in year_labels:
            card.add_column(label, justify="right")
        if show_totals:
            card.add_column("Total", justify="right")

        period_items = {
            label: _breakdown_for(breakdowns, username, label, row.get(label, 0))
            for label in year_labels
        }
        summed = sum_breakdowns(period_items.values())

        for key, cat_label, total_val in summed.categories(include_other=include_other):
            cat_cells = [cat_label]
            for label in year_labels:
                item = period_items[label]
                value = item.other if key == "other" else getattr(item, key)
                cat_cells.append(
                    _rich_text(
                        _format_category_value(
                            value, item.total, show_percent=show_percent
                        )
                    )
                )
            if show_totals:
                cat_cells.append(
                    _rich_text(
                        _format_category_value(
                            total_val, summed.total, show_percent=show_percent
                        )
                    )
                )
            card.add_row(*cat_cells)

        total_cells = [Text("Total", style="bold")]
        for label in year_labels:
            count = row.get(label, 0)
            total_cells.append(
                _rich_text(
                    _format_headline_cell(
                        count,
                        username,
                        col_values[label],
                        year_totals[label],
                        show_percent=show_percent,
                        redact_map=redact_map,
                        github_url=github_url,
                    )
                )
            )
        if show_totals:
            total_cells.append(Text(str(summed.total), style="bold"))
        card.add_section()
        card.add_row(*total_cells)
        cards.append(_render_rich_to_string(card))

    return "\n\n".join(cards)


def _render_columns(
    sorted_rows,
    ranks,
    year_labels,
    breakdowns,
    *,
    show_totals,
    show_percent,
    show_rank_delta,
    rank_deltas,
    ghost_usernames,
    redact_map,
    github_url,
    include_other,
):
    """Render one flat category-columns table per period, stacked newest-first."""
    sample_cats = ContributionBreakdown().categories(include_other=include_other)
    cat_keys = [key for key, _label, _val in sample_cats]
    cat_headers = [label for _key, label, _val in sample_cats]

    headers = (
        ["#"]
        + (["±"] if show_rank_delta else [])
        + ["Operative"]
        + cat_headers
        + ["Total"]
    )
    colalign = (
        ("right",)
        + (("center",) if show_rank_delta else ())
        + ("left",)
        + ("right",) * (len(cat_keys) + 1)
    )

    sections = []
    for period_label in year_labels:
        period_totals = [r.get(period_label, 0) for r in sorted_rows]
        cohort_total = sum(period_totals)
        table_data = []
        col_sums = {key: 0 for key in cat_keys}

        for rank, row in zip(ranks, sorted_rows):
            username = row["username"]
            is_ghost = ghost_usernames is not None and username in ghost_usernames
            display_name = redact_map.get(username) if redact_map else None
            count = row.get(period_label, 0)
            item = _breakdown_for(breakdowns, username, period_label, count)

            cells = [rank]
            if show_rank_delta:
                cells.append(ui.rank_delta_cell(rank_deltas.get(username)))
            cells.append(
                ui.make_operative_cell(
                    username,
                    is_ghost=is_ghost,
                    display_name=display_name,
                    github_url=github_url,
                )
            )
            for key in cat_keys:
                value = item.other if key == "other" else getattr(item, key)
                col_sums[key] += value
                cells.append(
                    _format_category_value(value, item.total, show_percent=show_percent)
                )
            cells.append(
                _format_headline_cell(
                    count,
                    username,
                    period_totals,
                    cohort_total,
                    show_percent=show_percent,
                    redact_map=redact_map,
                    github_url=github_url,
                )
            )
            table_data.append(cells)

        if show_totals:
            footer = [""]
            if show_rank_delta:
                footer.append("")
            footer.append("Total")
            for key in cat_keys:
                footer.append(col_sums[key])
            footer.append(cohort_total)
            table_data.append(footer)

        rendered = tabulate(
            table_data,
            headers=headers,
            tablefmt="simple",
            colalign=colalign,
        )
        sections.append(f"📅 {period_label}\n{rendered}")

    return "\n\n".join(sections)


def render_breakdown_table(  # noqa: PLR0913
    rows,
    year_labels,
    breakdowns,
    style="subrows",
    *,
    year_fraction=1.0,
    show_trend=True,
    show_totals=False,
    show_percent=False,
    show_rank_delta=True,
    rank_deltas=None,
    ghost_usernames=None,
    redact_map=None,
    github_url="https://github.com",
):
    """Render contribution breakdowns in one of the four terminal layouts.

    Args:
        rows: Contribution rows keyed by username and period label.
        year_labels: Ordered period labels, newest first.
        breakdowns: Nested mapping ``username -> period -> ContributionBreakdown``.
        style: One of ``subrows``, ``nested``, ``cards``, or ``columns``.
    """
    if style not in VALID_BREAKDOWN_STYLES:
        raise ValueError(
            f"Unknown breakdown style '{style}'. Valid styles: {VALID_BREAKDOWN_STYLES}"
        )
    if not rows:
        return "(no operatives configured)"

    sorted_rows, ranks = ui.sorted_rows_and_ranks(rows, year_labels)
    effective_trend = show_trend and len(year_labels) >= 2
    effective_rank_delta = show_rank_delta and rank_deltas is not None
    include_other = has_other_contributions(
        breakdowns,
        users=[row["username"] for row in sorted_rows],
        period_labels=year_labels,
    )

    if style == "subrows":
        return _render_subrows(
            sorted_rows,
            ranks,
            year_labels,
            breakdowns,
            year_fraction=year_fraction,
            show_trend=effective_trend,
            show_totals=show_totals,
            show_percent=show_percent,
            show_rank_delta=effective_rank_delta,
            rank_deltas=rank_deltas,
            ghost_usernames=ghost_usernames,
            redact_map=redact_map,
            github_url=github_url,
            include_other=include_other,
        )
    if style == "nested":
        return _render_nested(
            sorted_rows,
            ranks,
            year_labels,
            breakdowns,
            year_fraction=year_fraction,
            show_trend=effective_trend,
            show_totals=show_totals,
            show_percent=show_percent,
            show_rank_delta=effective_rank_delta,
            rank_deltas=rank_deltas,
            ghost_usernames=ghost_usernames,
            redact_map=redact_map,
            github_url=github_url,
            include_other=include_other,
        )
    if style == "cards":
        return _render_cards(
            sorted_rows,
            ranks,
            year_labels,
            breakdowns,
            year_fraction=year_fraction,
            show_trend=effective_trend,
            show_totals=show_totals,
            show_percent=show_percent,
            show_rank_delta=effective_rank_delta,
            rank_deltas=rank_deltas,
            ghost_usernames=ghost_usernames,
            redact_map=redact_map,
            github_url=github_url,
            include_other=include_other,
        )
    return _render_columns(
        sorted_rows,
        ranks,
        year_labels,
        breakdowns,
        show_totals=show_totals,
        show_percent=show_percent,
        show_rank_delta=effective_rank_delta,
        rank_deltas=rank_deltas,
        ghost_usernames=ghost_usernames,
        redact_map=redact_map,
        github_url=github_url,
        include_other=include_other,
    )
