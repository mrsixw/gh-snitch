import os
import re
import sys

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


def render_table(rows, year_labels, year_fraction=1.0, show_trend=True):
    """Render contribution data as a formatted table string.

    Args:
        rows: list of dicts with keys "username" and one key per year label (int values)
        year_labels: list of year label strings (first = current year)
        year_fraction: proportion of the current year elapsed (0–1], used to
            annualize current-year counts for trend comparison
        show_trend: whether to include the Trend column (requires >= 2 year labels)
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

    headers = ["#", "Operative"] + (["Trend"] if show_trend else []) + year_labels

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
            contrib_url = f"https://github.com/{username}"
            cells.append(
                make_coloured_hyperlink_cell(count, contrib_url, col_values[label])
            )
        table_data.append(cells)

    n_year_cols = len(year_labels)
    trend_align = ("center",) if show_trend else ()
    colalign = ("right",) + ("left",) + trend_align + ("right",) * n_year_cols
    return tabulate(
        table_data,
        headers=headers,
        tablefmt="simple",
        colalign=colalign,
    )
