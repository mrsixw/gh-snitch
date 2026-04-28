import calendar
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_URL = "https://github.com"
SECRET_GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


def graphql_url_for(github_url: str) -> str:
    """Return the GraphQL API endpoint for a given GitHub base URL.

    github.com uses a different hostname for its API (api.github.com),
    while GitHub Enterprise Server exposes the API at <host>/api/graphql.
    """
    url = github_url.rstrip("/")
    if url == "https://github.com":
        return "https://api.github.com/graphql"
    return f"{url}/api/graphql"


def make_github_graphql_request(query, github_url: str = DEFAULT_GITHUB_URL):
    """POST a GraphQL query to GitHub's API and return the response JSON."""
    headers = {
        "Authorization": f"bearer {SECRET_GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        graphql_url_for(github_url),
        json={"query": query},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if "errors" in data:
        fatal_errors = [e for e in data["errors"] if e.get("type") != "NOT_FOUND"]
        if fatal_errors:
            raise ValueError(f"GraphQL errors: {fatal_errors}")
        for err in data["errors"]:
            logger.warning("operative not found: %s", err.get("message", err))
    return data


def current_year_fraction() -> float:
    """Return the fraction of the current calendar year that has elapsed (0–1].

    Used to annualize partial-year contribution counts for trend comparison.
    """
    today = date.today()
    days_in_year = 366 if calendar.isleap(today.year) else 365
    day_of_year = (today - date(today.year, 1, 1)).days + 1
    return day_of_year / days_in_year


def get_year_ranges(years):
    """Return a list of (label, from_iso, to_iso) tuples.

    First entry is the current year (Jan 1 → today).
    Then `years` prior complete years (Jan 1 → Dec 31).
    """
    today = date.today()
    current_year = today.year
    ranges = []

    # Current year: Jan 1 → today
    from_dt = datetime(current_year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    to_dt = datetime(
        today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc
    )
    ranges.append((str(current_year), from_dt.isoformat(), to_dt.isoformat()))

    # Prior complete years
    for i in range(1, years + 1):
        year = current_year - i
        from_dt = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        to_dt = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        ranges.append((str(year), from_dt.isoformat(), to_dt.isoformat()))

    return ranges


VALID_PERIODS = ("week", "month", "year")


def get_period_range(period: str) -> tuple[str, str, str]:
    """Return a (label, from_iso, to_iso) tuple for a named time period.

    Supported periods:
      'week'  — Monday of the current ISO week → today
      'month' — 1st of the current month → today
      'year'  — January 1st of the current year → today
    """
    today = date.today()
    to_dt = datetime(
        today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc
    )

    if period == "week":
        monday = today - timedelta(days=today.weekday())
        from_dt = datetime(
            monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=timezone.utc
        )
        label = "This Week"
    elif period == "month":
        from_dt = datetime(today.year, today.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        label = "This Month"
    elif period == "year":
        from_dt = datetime(today.year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        label = "This Year"
    else:
        raise ValueError(f"Unknown period '{period}'. Valid periods: {VALID_PERIODS}")

    return label, from_dt.isoformat(), to_dt.isoformat()


def build_contributions_query(users, from_iso, to_iso):
    """Build a GraphQL query with aliases for each user."""
    aliases = []
    for i, username in enumerate(users):
        alias = f"user_{i}"
        aliases.append(f"""
  {alias}: user(login: "{username}") {{
    login
    contributionsCollection(from: "{from_iso}", to: "{to_iso}") {{
      contributionCalendar {{
        totalContributions
      }}
    }}
  }}""")
    return "{ " + "".join(aliases) + " }"


def _fetch_year(users, label, from_iso, to_iso, github_url):
    """Fetch contributions for all users for a single year range."""
    logger.debug(
        "fetching year=%s users=%s from=%s to=%s", label, users, from_iso, to_iso
    )
    query = build_contributions_query(users, from_iso, to_iso)
    data = make_github_graphql_request(query, github_url)
    logger.debug("year=%s response received", label)
    return label, data.get("data", {})


def get_rolling_month_ranges(n: int) -> list[tuple[str, str, str]]:
    """Return the last n calendar months as (label, from_iso, to_iso) tuples.

    Most recent month first.  The current (partial) month is entry 0; prior
    complete months follow.  Labels use the format 'Apr 2026'.
    """
    today = date.today()
    ranges = []
    year, month = today.year, today.month
    for i in range(n):
        from_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
        if i == 0:
            end_day = today.day
        else:
            end_day = calendar.monthrange(year, month)[1]
        to_dt = datetime(year, month, end_day, 23, 59, 59, tzinfo=timezone.utc)
        label = from_dt.strftime("%b %Y")
        ranges.append((label, from_dt.isoformat(), to_dt.isoformat()))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return ranges


def get_rolling_week_ranges(n: int) -> list[tuple[str, str, str]]:
    """Return the last n ISO weeks as (label, from_iso, to_iso) tuples.

    Most recent week first.  The current (partial) week is entry 0; prior
    complete weeks (Mon–Sun) follow.  Labels use the format '2026-W15'.
    """
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    ranges = []
    for i in range(n):
        monday = current_monday - timedelta(weeks=i)
        week_end = today if i == 0 else monday + timedelta(days=6)
        from_dt = datetime(
            monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=timezone.utc
        )
        to_dt = datetime(
            week_end.year, week_end.month, week_end.day, 23, 59, 59, tzinfo=timezone.utc
        )
        iso_year, iso_week, _ = monday.isocalendar()
        label = f"{iso_year}-W{iso_week:02d}"
        ranges.append((label, from_dt.isoformat(), to_dt.isoformat()))
    return ranges


def get_custom_range(since: str, until: str | None = None) -> tuple[str, str, str]:
    """Return a (label, from_iso, to_iso) for an arbitrary date range.

    since and until are YYYY-MM-DD strings; until defaults to today.
    Raises ValueError for invalid or out-of-order dates.
    """
    try:
        from_date = date.fromisoformat(since)
    except ValueError:
        raise ValueError(f"Invalid date '{since}'. Expected YYYY-MM-DD.")
    to_date = date.today()
    if until is not None:
        try:
            to_date = date.fromisoformat(until)
        except ValueError:
            raise ValueError(f"Invalid date '{until}'. Expected YYYY-MM-DD.")
    if from_date > to_date:
        raise ValueError(f"--since ({since}) must not be after --until ({to_date}).")
    from_dt = datetime(
        from_date.year, from_date.month, from_date.day, 0, 0, 0, tzinfo=timezone.utc
    )
    to_dt = datetime(
        to_date.year, to_date.month, to_date.day, 23, 59, 59, tzinfo=timezone.utc
    )
    label = f"{since}–{to_date.isoformat()}" if until else f"Since {since}"
    return label, from_dt.isoformat(), to_dt.isoformat()


def fetch_contributions(
    users,
    years,
    github_url: str = DEFAULT_GITHUB_URL,
    on_progress=None,
    *,
    period=None,
    year_ranges=None,
):
    """Fetch contribution counts for all users across year ranges.

    Requests are dispatched concurrently — one per year range.
    Returns (dict[username][label] = int, set[not_found_usernames]).
    Usernames that could not be resolved on GitHub appear in the not_found set
    with zero contributions in the result dict.
    on_progress, if provided, is called with (completed, total) after each year.

    year_ranges (explicit list of (label, from_iso, to_iso) tuples) takes
    highest precedence.  When period is set, a single named-window range is
    used.  Otherwise get_year_ranges(years) is called.
    """
    if year_ranges is not None:
        ranges = year_ranges
    elif period is not None:
        ranges = [get_period_range(period)]
    else:
        ranges = get_year_ranges(years)
    total = len(ranges)
    result = {username: {} for username in users}
    null_counts: dict[str, int] = {username: 0 for username in users}

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(_fetch_year, users, label, from_iso, to_iso, github_url)
            for label, from_iso, to_iso in ranges
        }

        for completed, future in enumerate(as_completed(futures), start=1):
            label, response_data = future.result()

            for i, username in enumerate(users):
                alias = f"user_{i}"
                user_data = response_data.get(alias)
                if user_data is None:
                    logger.warning(
                        "no data returned for user=%s year=%s", username, label
                    )
                    result[username][label] = 0
                    null_counts[username] += 1
                else:
                    count = (
                        user_data.get("contributionsCollection", {})
                        .get("contributionCalendar", {})
                        .get("totalContributions", 0)
                    )
                    result[username][label] = count
                    logger.debug(
                        "user=%s year=%s contributions=%d", username, label, count
                    )

            if on_progress is not None:
                on_progress(completed, total)

    not_found = {u for u, c in null_counts.items() if c == total}
    return result, not_found
