import os
import re
import sys
from datetime import datetime

import tabulate as _tabulate_module
from tabulate import tabulate

IS_TTY = sys.stdout.isatty() and not os.getenv("NO_COLOR")

# Patch tabulate to strip OSC 8 hyperlink sequences when measuring column widths.
# Without this, tabulate counts invisible escape bytes as visible characters,
# causing grossly over-wide columns and broken alignment.
_OSC8_RE = re.compile(r"\x1b\]8;[^;]*;[^\x1b]*\x1b\\")
_orig_visible_width = _tabulate_module._visible_width


def _patched_visible_width(s):
    return _orig_visible_width(_OSC8_RE.sub("", str(s)))


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


def make_operative_cell(username):
    """Return a hyperlinked username cell."""
    url = f"https://github.com/{username}"
    return make_hyperlink(url, username)


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


def _easter_month(year):
    """Return the month (3 or 4) that Easter Sunday falls in for the given year."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lo = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lo) // 451
    return (h + lo - 7 * m + 114) // 31


def _delta_palette():
    """Return the colour palette list for delta cells based on the current month."""
    month = datetime.now().month
    year = datetime.now().year
    if month == 1:
        return _DELTA_PALETTES["purple"]
    if month == _easter_month(year):
        return _DELTA_PALETTES["yellow"]
    if month == 10:
        return _DELTA_PALETTES["orange"]
    if month == 12:
        return _DELTA_PALETTES["red"]
    return _DELTA_PALETTES["green"]


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


def render_table(
    rows,
    year_labels,
    year_fraction=1.0,
    show_trend=True,
    show_totals=False,
    show_percent=False,
    delta_col=None,
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
        delta_col: label of the column whose values are deltas (rendered with +/- and
            green/red colouring instead of percentile-based grading)
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

    headers = (
        ["#", "Operative"]
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
        profile_url = f"https://github.com/{username}"
        cells = [rank, make_hyperlink(profile_url, username)]
        if show_trend:
            current = row.get(year_labels[0], 0)
            previous = row.get(year_labels[1], 0)
            cells.append(_trend_indicator(current, previous, year_fraction))
        for label in year_labels:
            count = row.get(label, 0)
            if label == delta_col:
                cells.append(_delta_cell(count, col_values[label]))
            else:
                contrib_url = f"https://github.com/{username}"
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
        totals_cells = ["", "Total"]
        if show_trend:
            totals_cells.append("")
        for label in year_labels:
            totals_cells.append(year_totals[label])
        totals_cells.append(sum(year_totals.values()))
        table_data.append(totals_cells)

    n_year_cols = len(year_labels)
    trend_align = ("center",) if show_trend else ()
    total_align = ("right",) if show_totals else ()
    colalign = (
        ("right",) + ("left",) + trend_align + ("right",) * n_year_cols + total_align
    )
    return tabulate(
        table_data,
        headers=headers,
        tablefmt="simple",
        colalign=colalign,
    )
