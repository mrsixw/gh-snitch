import os
import sys

from tabulate import tabulate

IS_TTY = sys.stdout.isatty() and not os.getenv("NO_COLOR")


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


def render_table(rows, year_labels):
    """Render contribution data as a formatted table string.

    Args:
        rows: list of dicts with keys "username" and one key per year label (int values)
        year_labels: list of year label strings (first = current year)
    """
    if not rows:
        return "(no operatives configured)"

    current_year_label = year_labels[0]

    # Sort descending by current year, then alpha by username
    sorted_rows = sorted(
        rows,
        key=lambda r: (-r.get(current_year_label, 0), r["username"]),
    )

    # Build per-column value lists for colour grading
    col_values = {}
    for label in year_labels:
        col_values[label] = [r.get(label, 0) for r in sorted_rows]

    headers = ["Operative"] + year_labels

    table_data = []
    for row in sorted_rows:
        username = row["username"]
        profile_url = f"https://github.com/{username}"
        cells = [make_hyperlink(profile_url, username)]
        for label in year_labels:
            count = row.get(label, 0)
            contrib_url = f"https://github.com/{username}"
            cells.append(
                make_coloured_hyperlink_cell(count, contrib_url, col_values[label])
            )
        table_data.append(cells)

    n_year_cols = len(year_labels)
    return tabulate(
        table_data,
        headers=headers,
        tablefmt="simple",
        colalign=("left",) + ("right",) * n_year_cols,
    )
