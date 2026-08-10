import csv as _csv
import io
import json as _json
import os
import re
import sys
import unicodedata
from datetime import datetime

import asciichartpy as ac
import tabulate as _tabulate_module
from tabulate import tabulate

IS_TTY = sys.stdout.isatty() and not os.getenv("NO_COLOR")

# Patch tabulate to correctly measure column widths when cells contain OSC 8
# hyperlink sequences or wide Unicode characters (e.g. emoji).
#
# Without this patch two things go wrong:
#   1. Tabulate counts invisible OSC 8 escape bytes as visible characters,
#      producing grossly over-wide columns.
#   2. Without the optional `wcwidth` package installed, tabulate falls back to
#      len(), which counts wide characters (East Asian Width W/F, which includes
#      emoji like 👻) as 1 column even though terminals render them as 2. This
#      causes a 1-column misalignment on every row that contains such a character.
#
# The fix strips OSC 8 sequences and then uses unicodedata (stdlib) to tally
# visual width, counting W/F characters as 2 and everything else as 1.
_OSC8_RE = re.compile(r"\x1b\]8;[^;]*;[^\x1b]*\x1b\\")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _patched_visible_width(s):
    s = _OSC8_RE.sub("", str(s))
    s = _ANSI_RE.sub("", s)
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


_tabulate_module._visible_width = _patched_visible_width


def _percentile(values, p):
    """Return the p-th percentile of values (0-100)."""
    if not values:
        return 0
    sorted_vals = sorted(values)
    index = (p / 100) * (len(sorted_vals) - 1)
    lower = int(index)
    upper = lower + 1
    if upper >= len(sorted_vals):
        return sorted_vals[-1]
    frac = index - lower
    return sorted_vals[lower] + frac * (sorted_vals[upper] - sorted_vals[lower])


def _grade_colour(count, column_values):
    """Return (prefix, suffix) ANSI escape strings for the given count.

    Grading is based on percentiles within non-zero column values.
    """
    reset = "\033[0m"

    if count == 0:
        return "\033[2;37m", reset

    non_zero = [v for v in column_values if v > 0]
    if not non_zero:
        return "\033[2;37m", reset

    p25 = _percentile(non_zero, 25)
    p50 = _percentile(non_zero, 50)
    p75 = _percentile(non_zero, 75)

    if count <= p25:
        return "\033[31m", reset  # red
    elif count <= p50:
        return "\033[33m", reset  # yellow
    elif count <= p75:
        return "\033[32m", reset  # green
    else:
        return "\033[1;32m", reset  # bright green


def make_hyperlink(url, text):
    """Return an OSC 8 hyperlink if TTY, else plain text."""
    if IS_TTY:
        return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"
    return text


def make_coloured_hyperlink_cell(count, url, column_values):
    """Return a cell string combining colour and OSC 8 hyperlink."""
    if IS_TTY:
        prefix, suffix = _grade_colour(count, column_values)
        return f"\033]8;;{url}\033\\{prefix}{count}{suffix}\033]8;;\033\\"
    return str(count)


def make_operative_cell(
    username, is_ghost=False, display_name=None, github_url="https://github.com"
):
    """Return an operative name cell.

    When display_name is provided (redact mode) the cell is plain text with no
    hyperlink.  Otherwise a clickable OSC 8 link to the GitHub profile is used.
    """
    if display_name is not None:
        ghost_mark = (" 👻" if IS_TTY else " [ghost]") if is_ghost else ""
        return display_name + ghost_mark
    url = f"{github_url.rstrip('/')}/{username}"
    link = make_hyperlink(url, username)
    if not is_ghost:
        return link
    ghost_mark = " 👻" if IS_TTY else " [ghost]"
    return link + ghost_mark


# ---------------------------------------------------------------------------
# Delta cell colouring
#
# Zero delta → dim red (no activity this period).
# Positive delta → graduated colour dark→bright based on percentile rank
# within the column.  The colour palette rotates by month — a small easter
# egg for attentive operatives:
#
#   January  → purple  (handler's birthday)
#   March/April (Easter month, computed per year) → yellow
#   October  → orange  (Halloween)
#   December → red     (Christmas)
#   all other months   → green  (default surveillance mode)
# ---------------------------------------------------------------------------

_DELTA_ZERO = "\033[2;31m"  # dim red — no activity

# 256-colour palettes: 4 shades, darkest → brightest
_DELTA_PALETTES = {
    "green": ["\033[38;5;22m", "\033[38;5;34m", "\033[38;5;40m", "\033[38;5;46m"],
    "purple": ["\033[38;5;54m", "\033[38;5;90m", "\033[38;5;129m", "\033[38;5;165m"],
    "yellow": ["\033[38;5;136m", "\033[38;5;178m", "\033[38;5;220m", "\033[38;5;226m"],
    "orange": ["\033[38;5;130m", "\033[38;5;166m", "\033[38;5;202m", "\033[38;5;208m"],
    "red": ["\033[38;5;88m", "\033[38;5;124m", "\033[38;5;160m", "\033[38;5;196m"],
}


def _easter_month():
    """Return the month (3 or 4) that Easter Sunday falls in for the current year.

    Uses the Anonymous Gregorian algorithm (Meeus/Jones/Butcher), which works
    by layering three interlocking corrections on top of a simple lunar cycle:

    1. Golden number — where the current year sits in the 19-year Metonic cycle
       (after 19 solar years, lunar phases recur on the same calendar dates).

    2. Epact — the age of the moon on 1 January, derived from the golden number
       then adjusted for two Gregorian-calendar corrections that the older Julian
       algorithm ignored:
         - The century leap correction accounts for the dropped leap years in
           century years (e.g. 1900 was not a leap year).
         - The lunar correction accounts for the accumulated drift of the
           Gregorian calendar's lunar approximation over the centuries.

    3. Weekday offset — pushes the date forward to the following Sunday, since
       Easter is defined as the first Sunday after the first full moon on or
       after the spring equinox (21 March).

    4. Metonic adjustment — a final correction for the two rare cases where the
       raw result lands on one of the historically excluded dates (April 26 or
       a full-moon Easter that would coincide with a Jewish Passover).

    Throughout, // is Python's floor-division operator: it divides and discards
    the remainder, returning only the whole-number part (e.g. 7 // 2 == 3).
    This is essential wherever the algorithm needs a count of complete cycles
    rather than a fractional quantity.
    """
    year = datetime.now().year
    golden_number = year % 19
    century, year_of_century = divmod(year, 100)
    century_leap_correction = century // 4  # dropped leap years in century years
    century_remainder = century % 4
    gregorian_correction = (century + 8) // 25  # accumulated Gregorian lunar drift
    lunar_correction = (century - gregorian_correction + 1) // 3
    epact = (
        19 * golden_number + century - century_leap_correction - lunar_correction + 15
    ) % 30  # age of moon on 1 Jan, adjusted for Gregorian corrections
    year_leap_days, year_leap_remainder = divmod(year_of_century, 4)
    weekday_offset = (
        32 + 2 * century_remainder + 2 * year_leap_days - epact - year_leap_remainder
    ) % 7  # days to advance to reach the next Sunday
    metonic_adjustment = (golden_number + 11 * epact + 22 * weekday_offset) // 451
    return (epact + weekday_offset - 7 * metonic_adjustment + 114) // 31


# Map each month to its palette name; Easter month is resolved at call time.
_MONTH_PALETTE_NAMES = {
    1: "purple",
    10: "orange",
    12: "red",
}


def _delta_palette():
    """Return the colour palette list for delta cells based on the current month."""
    now = datetime.now()
    month = now.month
    if now.month == _easter_month():
        return _DELTA_PALETTES["yellow"]
    return _DELTA_PALETTES[_MONTH_PALETTE_NAMES.get(month, "green")]


def _delta_cell(delta, col_values):
    """Return a coloured cell string for a delta (change) value.

    Zero (or negative) → dim red.  Positive → graduated dark→bright using
    the current month's palette, ranked by percentile within col_values.
    """
    if delta <= 0:
        text = str(delta) if delta < 0 else "0"
        return f"{_DELTA_ZERO}{text}\033[0m" if IS_TTY else text

    text = f"+{delta}"
    if not IS_TTY:
        return text

    palette = _delta_palette()
    non_zero = [v for v in col_values if v > 0]
    if not non_zero or len(non_zero) == 1:
        colour = palette[-1]
    else:
        p25 = _percentile(non_zero, 25)
        p50 = _percentile(non_zero, 50)
        p75 = _percentile(non_zero, 75)
        if delta <= p25:
            colour = palette[0]
        elif delta <= p50:
            colour = palette[1]
        elif delta <= p75:
            colour = palette[2]
        else:
            colour = palette[3]
    return f"{colour}{text}\033[0m"


def _rank_delta_cell(delta):
    """Return a formatted rank-delta string for the ± column.

    Positive delta means the operative moved up (lower rank number = better).
    Negative means they dropped. Zero means no change. None means new operative.
    """
    if delta is None:
        text = "new"
        return f"\033[2m{text}\033[0m" if IS_TTY else text
    if delta == 0:
        text = "="
        return f"\033[2m{text}\033[0m" if IS_TTY else text
    if delta > 0:
        text = f"↑{delta}" if IS_TTY else f"+{delta}"
        return f"\033[32m{text}\033[0m" if IS_TTY else text
    text = f"↓{abs(delta)}" if IS_TTY else f"-{abs(delta)}"
    return f"\033[31m{text}\033[0m" if IS_TTY else text


def _trend_indicator(current, previous, year_fraction):
    """Return a YoY trend indicator string for one operative.

    Compares an annualized current-year count to the previous full year:
      >= 10% increase → ↑ (green in TTY, '+' plain)
      <= 10% decrease → ↓ (red in TTY,  '-' plain)
      within ±10%     → → (dim in TTY,  '=' plain)

    year_fraction is the proportion of the current year elapsed (0–1], used to
    project the current count to a full-year rate before comparison. For example,
    100 contributions by day 82 of 365 (≈22% through the year) projects to
    100 / 0.225 ≈ 444 — a fair comparison against last year's full total.
    Note: this assumes a linear contribution rate, which may not reflect real
    patterns (e.g. conference bursts, quieter summer months).

    When previous is 0, any positive projected count is treated as an increase.
    """
    effective = current / year_fraction

    if previous == 0:
        if effective > 0:
            sym = "↑" if IS_TTY else "+"
            return f"\033[32m{sym}\033[0m" if IS_TTY else sym
        sym = "→" if IS_TTY else "="
        return f"\033[2m{sym}\033[0m" if IS_TTY else sym

    change = (effective - previous) / previous
    if change >= 0.10:
        sym = "↑" if IS_TTY else "+"
        return f"\033[32m{sym}\033[0m" if IS_TTY else sym
    elif change <= -0.10:
        sym = "↓" if IS_TTY else "-"
        return f"\033[31m{sym}\033[0m" if IS_TTY else sym
    else:
        sym = "→" if IS_TTY else "="
        return f"\033[2m{sym}\033[0m" if IS_TTY else sym


def _sorted_rows_and_ranks(rows, year_labels):
    """Return (sorted_rows, ranks) sorted descending by first label then alpha."""
    current_label = year_labels[0]
    sorted_rows = sorted(rows, key=lambda r: (-r.get(current_label, 0), r["username"]))
    ranks = []
    for i, row in enumerate(sorted_rows):
        if i == 0:
            ranks.append(1)
        else:
            prev = sorted_rows[i - 1].get(current_label, 0)
            curr = row.get(current_label, 0)
            ranks.append(ranks[-1] if curr == prev else i + 1)
    return sorted_rows, ranks


def _tabular_records(rows, period_labels, show_totals=False, redact_map=None):
    """Return ranked plain-data records shared by structured renderers.

    Args:
        rows: Contribution rows keyed by username and period label.
        period_labels: Ordered period labels to include.
        show_totals: Whether to include a per-operative total.
        redact_map: Optional username-to-codename mapping.

    Returns:
        list[dict]: Ranked records without terminal formatting.
    """
    if not rows:
        return []
    sorted_rows, ranks = _sorted_rows_and_ranks(rows, period_labels)
    records = []
    for rank, row in zip(ranks, sorted_rows):
        username = row["username"]
        operative_name = redact_map.get(username, username) if redact_map else username
        record = {"rank": rank, "operative": operative_name}
        for label in period_labels:
            record[label] = row.get(label, 0)
        if show_totals:
            record["total"] = sum(row.get(label, 0) for label in period_labels)
        records.append(record)
    return records


def render_json(rows, year_labels, show_totals=False, redact_map=None):
    """Render contribution data as a JSON array (no ANSI codes).

    Each element is an object with "rank", "operative", one key per period
    label, and optionally "total" when show_totals is True.
    """
    records = _tabular_records(
        rows, year_labels, show_totals=show_totals, redact_map=redact_map
    )
    return _json.dumps(records, indent=2, ensure_ascii=False)


def render_multi_json(reports, show_totals=False, redact_map=None):
    """Render multiple independent team reports as structured JSON.

    Args:
        reports: Ordered contribution reports, one per selected team.
        show_totals: Whether to include per-operative totals.
        redact_map: Optional username-to-codename mapping.

    Returns:
        str: JSON object retaining explicit team boundaries.
    """
    teams = []
    for report in reports:
        teams.append(
            {
                "team": report.name,
                "operatives": _tabular_records(
                    report.rows,
                    report.period_labels,
                    show_totals=show_totals,
                    redact_map=redact_map,
                ),
            }
        )
    return _json.dumps({"teams": teams}, indent=2, ensure_ascii=False)


def render_csv(rows, year_labels, show_totals=False, redact_map=None):
    """Render contribution data as CSV (no ANSI codes).

    Header row: rank, operative, <period labels…> [, total]
    One data row per operative, and an optional totals footer row.
    """
    if not rows:
        return ""
    sorted_rows, ranks = _sorted_rows_and_ranks(rows, year_labels)
    fieldnames = (
        ["rank", "operative"] + year_labels + (["total"] if show_totals else [])
    )
    output = io.StringIO()
    writer = _csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for rank, row in zip(ranks, sorted_rows):
        username = row["username"]
        operative_name = redact_map.get(username, username) if redact_map else username
        record = {"rank": rank, "operative": operative_name}
        for label in year_labels:
            record[label] = row.get(label, 0)
        if show_totals:
            record["total"] = sum(row.get(label, 0) for label in year_labels)
        writer.writerow(record)
    if show_totals:
        year_totals = {
            label: sum(r.get(label, 0) for r in rows) for label in year_labels
        }
        footer = {"rank": "", "operative": "Total"}
        for label in year_labels:
            footer[label] = year_totals[label]
        footer["total"] = sum(year_totals.values())
        writer.writerow(footer)
    return output.getvalue()


def render_multi_csv(reports, show_totals=False, redact_map=None):
    """Render multiple team reports as one CSV with explicit team identity.

    Args:
        reports: Ordered contribution reports, one per selected team.
        show_totals: Whether to add per-operative and per-team totals.
        redact_map: Optional username-to-codename mapping.

    Returns:
        str: CSV containing a team column on every row.
    """
    period_labels = []
    populated_reports = [report for report in reports if report.rows]
    label_sources = populated_reports or reports
    for report in label_sources:
        for label in report.period_labels:
            if label not in period_labels:
                period_labels.append(label)

    fieldnames = (
        ["team", "rank", "operative"]
        + period_labels
        + (["total"] if show_totals else [])
    )
    output = io.StringIO()
    writer = _csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for report in reports:
        records = _tabular_records(
            report.rows,
            report.period_labels,
            show_totals=show_totals,
            redact_map=redact_map,
        )
        for record in records:
            writer.writerow({"team": report.name, **record})

        if show_totals and report.rows:
            footer = {"team": report.name, "rank": "", "operative": "Total"}
            for label in report.period_labels:
                footer[label] = sum(row.get(label, 0) for row in report.rows)
            footer["total"] = sum(footer[label] for label in report.period_labels)
            writer.writerow(footer)

    return output.getvalue()


def render_markdown(rows, year_labels, show_totals=False, redact_map=None):
    """Render contribution data as a GitHub-Flavoured Markdown table (no ANSI).

    Columns: # | Operative | <period labels…> [| Total]
    Includes a totals footer row when show_totals is True.
    """
    if not rows:
        return "(no operatives configured)"
    sorted_rows, ranks = _sorted_rows_and_ranks(rows, year_labels)
    headers = ["#", "Operative"] + year_labels + (["Total"] if show_totals else [])

    def _row(cells):
        return "| " + " | ".join(str(c) for c in cells) + " |"

    sep_parts = []
    for h in headers:
        sep_parts.append(":---" if h == "Operative" else "---:")
    separator = "| " + " | ".join(sep_parts) + " |"

    lines = [_row(headers), separator]
    for rank, row in zip(ranks, sorted_rows):
        username = row["username"]
        operative_name = redact_map.get(username, username) if redact_map else username
        cells = [rank, operative_name]
        for label in year_labels:
            cells.append(row.get(label, 0))
        if show_totals:
            cells.append(sum(row.get(label, 0) for label in year_labels))
        lines.append(_row(cells))

    if show_totals:
        year_totals = {
            label: sum(r.get(label, 0) for r in rows) for label in year_labels
        }
        footer = ["", "**Total**"]
        for label in year_labels:
            footer.append(year_totals[label])
        footer.append(sum(year_totals.values()))
        lines.append(_row(footer))

    return "\n".join(lines)


def render_multi_markdown(reports, show_totals=False, redact_map=None):
    """Render multiple team reports as labelled Markdown sections.

    Args:
        reports: Ordered contribution reports, one per selected team.
        show_totals: Whether to include totals in each team table.
        redact_map: Optional username-to-codename mapping.

    Returns:
        str: GitHub-Flavoured Markdown with one section per team.
    """
    sections = []
    for report in reports:
        table = render_markdown(
            report.rows,
            report.period_labels,
            show_totals=show_totals,
            redact_map=redact_map,
        )
        sections.append(f"## Team: {report.name}\n\n{table}")
    return "\n\n".join(sections)


def render_table(
    rows,
    year_labels,
    year_fraction=1.0,
    show_trend=True,
    show_totals=False,
    show_percent=False,
    show_rank_delta=True,
    delta_col=None,
    rank_deltas=None,
    ghost_usernames=None,
    redact_map=None,
    github_url="https://github.com",
):
    """Render contribution data as a formatted table string.

    Args:
        rows: list of dicts with keys "username" and one key per year label (int values)
        year_labels: list of year label strings (first = current year)
        year_fraction: proportion of the current year elapsed (0–1], used to
            annualize current-year counts for trend comparison
        show_trend: whether to include the Trend column (requires >= 2 year labels)
        show_totals: whether to add a Total column per operative and a Total footer row
        show_percent: whether to annotate each cell with (N%) share of that year's total
        show_rank_delta: whether to show the ± column (default: True)
        delta_col: label of the column whose values are deltas (rendered with +/- and
            green/red colouring instead of percentile-based grading)
        rank_deltas: optional dict[username, int | None] mapping each operative to their
            leaderboard movement since the previous run (positive = moved up,
            None = new operative). When provided, a ± column is shown after the
            # column.
        ghost_usernames: optional set of usernames with zero contributions across all
            surveilled periods. These operatives receive a 👻 (TTY) or [ghost]
            (non-TTY) indicator appended to their name cell.
        redact_map: optional dict mapping real usernames to NATO codenames. When
            provided, the codename replaces the username in the Operative column
            and no hyperlink is emitted (plain text only).
    """
    if not rows:
        return "(no operatives configured)"

    current_year_label = year_labels[0]
    show_trend = show_trend and len(year_labels) >= 2

    # Sort descending by current year, then alpha by username
    sorted_rows = sorted(
        rows,
        key=lambda r: (-r.get(current_year_label, 0), r["username"]),
    )

    # Build per-column value lists for colour grading
    col_values = {}
    for label in year_labels:
        col_values[label] = [r.get(label, 0) for r in sorted_rows]

    # Compute per-year totals (used for percentages and totals row)
    year_totals = {
        label: sum(r.get(label, 0) for r in sorted_rows) for label in year_labels
    }

    # Pre-compute per-year percentage lists for colour grading
    col_pct_values = {}
    if show_percent:
        for label in year_labels:
            total = year_totals[label]
            col_pct_values[label] = [
                (r.get(label, 0) / total * 100) if total > 0 else 0.0
                for r in sorted_rows
            ]

    show_rank_delta = show_rank_delta and rank_deltas is not None
    headers = (
        ["#"]
        + (["±"] if show_rank_delta else [])
        + ["Operative"]
        + (["Trend"] if show_trend else [])
        + year_labels
        + (["Total"] if show_totals else [])
    )

    # Compute competition ranks (1, 2, 2, 4, ...) based on current-year count
    ranks = []
    for i, row in enumerate(sorted_rows):
        if i == 0:
            ranks.append(1)
        else:
            prev_count = sorted_rows[i - 1].get(current_year_label, 0)
            curr_count = row.get(current_year_label, 0)
            ranks.append(ranks[-1] if curr_count == prev_count else i + 1)

    table_data = []
    for rank, row in zip(ranks, sorted_rows):
        username = row["username"]
        cells = [rank]
        if show_rank_delta:
            cells.append(_rank_delta_cell(rank_deltas.get(username)))
        is_ghost = ghost_usernames is not None and username in ghost_usernames
        display_name = redact_map.get(username) if redact_map else None
        cells.append(
            make_operative_cell(
                username,
                is_ghost=is_ghost,
                display_name=display_name,
                github_url=github_url,
            )
        )
        if show_trend:
            current = row.get(year_labels[0], 0)
            previous = row.get(year_labels[1], 0)
            cells.append(_trend_indicator(current, previous, year_fraction))
        for label in year_labels:
            count = row.get(label, 0)
            if label == delta_col:
                cells.append(_delta_cell(count, col_values[label]))
                continue
            if redact_map is not None:
                if IS_TTY:
                    prefix, suffix = _grade_colour(count, col_values[label])
                    cell = f"{prefix}{count}{suffix}"
                else:
                    cell = str(count)
            else:
                contrib_url = f"{github_url.rstrip('/')}/{username}"
                cell = make_coloured_hyperlink_cell(
                    count, contrib_url, col_values[label]
                )
            if show_percent:
                total = year_totals[label]
                pct = (count / total * 100) if total > 0 else 0.0
                if IS_TTY:
                    prefix, suffix = _grade_colour(pct, col_pct_values[label])
                    pct_annotation = f"({prefix}{pct:.0f}%{suffix})"
                else:
                    pct_annotation = f"({pct:.0f}%)"
                cell = f"{cell} {pct_annotation}"
            cells.append(cell)
        if show_totals:
            cells.append(sum(row.get(label, 0) for label in year_labels))
        table_data.append(cells)

    # Add totals footer row (neutral — no colour grading)
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

    n_year_cols = len(year_labels)
    rank_delta_align = ("center",) if show_rank_delta else ()
    trend_align = ("center",) if show_trend else ()
    total_align = ("right",) if show_totals else ()
    colalign = (
        ("right",)
        + rank_delta_align
        + ("left",)
        + trend_align
        + ("right",) * n_year_cols
        + total_align
    )
    return tabulate(
        table_data,
        headers=headers,
        tablefmt="simple",
        colalign=colalign,
    )


def render_graph(rows, year_labels, show_totals=False, redact_map=None):
    """Render contribution data as a time-series line graph string."""
    if not rows:
        return "(no operatives configured)"

    # Time periods on X-axis, chronological order
    x_labels = list(reversed(year_labels))

    # Sort rows by current-year count (descending) to match table order
    current_year_label = year_labels[0]
    sorted_rows = sorted(
        rows, key=lambda r: (-r.get(current_year_label, 0), r["username"])
    )

    # Adjust graph size based on terminal or defaults
    try:
        width, height = os.get_terminal_size()
        graph_height = max(10, min(height - 10, 20))
        # Leave room for Y-axis labels and some margin
        target_width = max(len(x_labels) * 4, width - 15)
    except (OSError, AttributeError):
        graph_height = 10
        target_width = len(x_labels) * 4

    # Interpolate data to stretch it horizontally
    all_series = []
    num_steps = len(x_labels)
    if num_steps > 1 and target_width > num_steps:
        for row in sorted_rows:
            raw_series = [float(row.get(label, 0)) for label in x_labels]
            interpolated = []
            for j in range(target_width):
                # Map j [0, target_width-1] to fractional index [0, num_steps-1]
                idx = j * (num_steps - 1) / (target_width - 1)
                left = int(idx)
                right = min(left + 1, num_steps - 1)
                frac = idx - left
                val = raw_series[left] + frac * (raw_series[right] - raw_series[left])
                interpolated.append(val)
            all_series.append(interpolated)
    else:
        for row in sorted_rows:
            series = [float(row.get(label, 0)) for label in x_labels]
            all_series.append(series)

    # Curate colors from asciichartpy
    ac_colors = [
        ac.lightcyan,
        ac.lightmagenta,
        ac.lightgreen,
        ac.lightyellow,
        ac.lightblue,
        ac.lightred,
        ac.cyan,
        ac.magenta,
        ac.green,
        ac.yellow,
        ac.blue,
        ac.red,
    ]

    config = {
        "height": graph_height,
        "colors": [ac_colors[i % len(ac_colors)] for i in range(len(sorted_rows))],
        "offset": 2,
    }

    # Generate the plot
    plot_output = ac.plot(all_series, config)

    # Construct the title and legend
    labels_str = " – ".join(x_labels)
    title = (
        "\n          🕵️  OPERATIVE SURVEILLANCE DOSSIER — "
        f"TREND ANALYSIS ({labels_str})\n"
    )

    legend_items = []
    reset = "\033[0m"
    for i, row in enumerate(sorted_rows):
        color_code = ac_colors[i % len(ac_colors)]
        if not IS_TTY:
            color_code = ""
            reset = ""
        name = (
            redact_map.get(row["username"], row["username"])
            if redact_map
            else row["username"]
        )
        legend_items.append(f"{color_code}{name}{reset}")

    legend = "          " + ", ".join(legend_items) + "\n"

    return f"{title}\n{plot_output}\n\n{legend}"


# ---------------------------------------------------------------------------
# Stacked bar chart
# ---------------------------------------------------------------------------

_ANSI_COLORS = [
    "\033[96m",  # bright cyan
    "\033[95m",  # bright magenta
    "\033[92m",  # bright green
    "\033[93m",  # bright yellow
    "\033[94m",  # bright blue
    "\033[91m",  # bright red
    "\033[36m",  # cyan
    "\033[35m",  # magenta
    "\033[32m",  # green
    "\033[33m",  # yellow
    "\033[34m",  # blue
    "\033[31m",  # red
]
_ANSI_RESET = "\033[0m"
_BLOCK = "█"


def render_stack(rows, year_labels, redact_map=None):
    """Render a stacked bar chart: one column per year, colour-coded by operative."""
    if not rows:
        return "(no operatives configured)"

    x_labels = list(reversed(year_labels))  # chronological left→right
    current_year_label = year_labels[0]

    # Sort operatives descending by current year (consistent with table order).
    sorted_rows = sorted(
        rows, key=lambda r: (-r.get(current_year_label, 0), r["username"])
    )

    def _display_name(row):
        u = row["username"]
        return redact_map.get(u, u) if redact_map else u

    # Per-year totals and per-operative per-year counts.
    year_totals = {
        label: sum(r.get(label, 0) for r in sorted_rows) for label in x_labels
    }
    overall_max = max(year_totals.values()) if year_totals else 1

    try:
        term_width, term_height = os.get_terminal_size()
        chart_height = max(8, min(term_height - 12, 20))
    except (OSError, AttributeError):
        term_width = 80
        chart_height = 12

    # Column width: enough to fit the year label (min 4), capped so all years fit.
    num_years = len(x_labels)
    y_axis_width = 7  # "  9999 ┤" style
    gap = 2
    col_width = max(
        4, min(10, (term_width - y_axis_width - gap) // max(num_years, 1) - gap)
    )

    # Build the chart row by row (top = chart_height, bottom = 0).
    # For each chart row r (1 = top), the threshold value it represents:
    #   threshold = overall_max * r / chart_height
    # A year column cell at row r is filled by operatives whose cumulative
    # contribution (from the bottom) reaches that threshold.

    # Stack order: smallest operative at bottom, largest at top.
    # reversed(sorted_rows) → least-current-year first, so it sits at the base.
    stack_order = list(reversed(sorted_rows))

    lines = []
    for chart_row in range(chart_height, 0, -1):
        # Value band this row represents: (prev_threshold, threshold].
        threshold = overall_max * chart_row / chart_height
        prev_threshold = overall_max * (chart_row - 1) / chart_height
        tick_val = round(threshold)

        # Y-axis label on labelled rows, continuation bar elsewhere.
        if chart_row == chart_height or chart_row % max(1, chart_height // 5) == 0:
            y_label = f"{tick_val:>{y_axis_width - 2}} ┤"
        else:
            y_label = " " * (y_axis_width - 1) + "│"

        cells = []
        for label in x_labels:
            total = year_totals[label]
            if total <= 0 or total < prev_threshold:
                # Year has no contributions, or total doesn't reach this band.
                cells.append(" " * col_width)
                continue

            # Find which operative owns the cumulative band containing prev_threshold.
            cumulative = 0.0
            cell_color = ""
            for op_i, row in enumerate(stack_order):
                cumulative += row.get(label, 0)
                if cumulative >= prev_threshold:
                    if IS_TTY:
                        cell_color = _ANSI_COLORS[op_i % len(_ANSI_COLORS)]
                    break

            block = _BLOCK * col_width
            cells.append(f"{cell_color}{block}{_ANSI_RESET}" if IS_TTY else block)

        lines.append(y_label + (" " * gap).join(cells))

    # X-axis baseline
    baseline = " " * y_axis_width + ("─" * col_width + "  ") * num_years
    lines.append(baseline)

    # Year labels centred under each column
    year_row = " " * y_axis_width
    for label in x_labels:
        year_row += label[:col_width].center(col_width) + "  "
    lines.append(year_row.rstrip())

    # Legend: left→right matches bottom→top stack order.
    legend_parts = []
    for i, row in enumerate(stack_order):
        name = _display_name(row)
        if IS_TTY:
            c = _ANSI_COLORS[i % len(_ANSI_COLORS)]
            legend_parts.append(f"{c}{_BLOCK}{_ANSI_RESET} {name}")
        else:
            legend_parts.append(f"{_BLOCK} {name}")
    legend = "  " + "   ".join(legend_parts)

    title = "\n          🕵️  OPERATIVE SURVEILLANCE DOSSIER — STACKED SURVEILLANCE\n"
    body = "\n".join(lines)
    return f"{title}\n{body}\n\n{legend}\n"
