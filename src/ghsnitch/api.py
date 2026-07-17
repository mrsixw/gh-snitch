import calendar
import logging
import os
import random
import threading
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_URL = "https://github.com"
SECRET_GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

_MAX_RETRIES = 3
_RETRY_STATUSES = {502, 503, 504}
_REQUEST_TIMEOUT = 30
_MAX_GRAPHQL_ERROR_TYPES = 3
_MAX_GRAPHQL_ERROR_MESSAGE_LENGTH = 120
_MAX_STORED_GRAPHQL_ERRORS = 10

_api_stats_lock = threading.Lock()
_api_stats_enabled = threading.Event()
_api_stats = {"graphql_calls": 0}


def configure_api_stats(enabled):
    """Reset GraphQL request statistics and configure collection for one run.

    This must be called before any request worker threads start. Statistics count
    every GraphQL POST attempt, including retries and requests that return errors.

    Args:
        enabled: Whether subsequent GraphQL request attempts should be counted.
    """
    with _api_stats_lock:
        _api_stats["graphql_calls"] = 0
        if enabled:
            _api_stats_enabled.set()
        else:
            _api_stats_enabled.clear()


def get_api_stats():
    """Return a thread-safe snapshot of the current API request statistics."""
    with _api_stats_lock:
        return dict(_api_stats)


def _record_graphql_call():
    """Record one GraphQL POST attempt when API statistics are enabled."""
    if not _api_stats_enabled.is_set():
        return
    with _api_stats_lock:
        _api_stats["graphql_calls"] += 1


def _bounded_message(value, limit=_MAX_GRAPHQL_ERROR_MESSAGE_LENGTH):
    """Return normalized text capped to a fixed display length.

    Args:
        value: Value to convert to a single-line string.
        limit: Maximum number of characters to return.

    Returns:
        str: Normalized, optionally truncated text.
    """
    message = " ".join(str(value).split()) or "No message provided"
    if len(message) > limit:
        return f"{message[: limit - 3]}..."
    return message


def _summarize_graphql_errors(errors):
    """Return a bounded GraphQL error summary grouped by type.

    Args:
        errors: GraphQL error objects returned by GitHub.

    Returns:
        str: Counts and one representative message for up to three error types.
    """
    counts = {}
    first_messages = {}
    for error in errors:
        if isinstance(error, dict):
            error_type = str(error.get("type") or "UNKNOWN")
            message = error.get("message") or "No message provided"
        else:
            error_type = "UNKNOWN"
            message = error
        counts[error_type] = counts.get(error_type, 0) + 1
        first_messages.setdefault(error_type, _bounded_message(message))

    summaries = []
    error_types = sorted(counts, key=lambda item: (-counts[item], item))
    for error_type in error_types[:_MAX_GRAPHQL_ERROR_TYPES]:
        summaries.append(
            f"{error_type}={counts[error_type]}: {first_messages[error_type]}"
        )

    omitted_types = len(counts) - len(summaries)
    if omitted_types > 0:
        summaries.append(f"{omitted_types} additional error type(s)")
    return "; ".join(summaries) or "no error details"


class GitHubGraphQLError(ValueError):
    """Raised when GitHub returns fatal GraphQL errors.

    Attributes:
        error_count: Total number of fatal errors in the response.
        errors: Bounded tuple of representative original error objects.
        summary: Bounded error summary grouped by type.
    """

    def __init__(self, errors):
        self.error_count = len(errors)
        self.errors = tuple(errors[:_MAX_STORED_GRAPHQL_ERRORS])
        self.summary = _summarize_graphql_errors(errors)
        super().__init__(f"GraphQL request failed: {self.summary}")


class GitHubGraphQLRateLimitError(GitHubGraphQLError):
    """Raised when GitHub reports a GraphQL rate-limit failure."""

    def __init__(self, errors, reset_at=None):
        self.reset_at = reset_at
        super().__init__(errors)


class GitHubGraphQLResourceLimitError(GitHubGraphQLError):
    """Raised when GitHub reports exhausted GraphQL query resources."""


def _rate_limit_reset_at(response):
    """Return a displayable UTC reset time from GitHub response headers.

    Args:
        response: ``requests`` response that may include rate-limit headers.

    Returns:
        str | None: UTC reset time, or ``None`` when absent or invalid.
    """
    reset_timestamp = response.headers.get("X-RateLimit-Reset")
    if reset_timestamp is None:
        return None
    try:
        reset_time = datetime.fromtimestamp(int(reset_timestamp), tz=timezone.utc)
    except (OSError, OverflowError, TypeError, ValueError):
        return None
    return reset_time.strftime("%Y-%m-%d %H:%M:%S UTC")


def _wait_before_retry(attempt, cancel_event=None):
    """Wait with exponential backoff before a retry attempt.

    Args:
        attempt: Zero-based attempt index; zero performs no wait.
        cancel_event: Optional sweep cancellation signal.

    Raises:
        CancelledError: If another concurrent range has already failed.
    """
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledError("surveillance sweep cancelled")
    if attempt == 0:
        return
    delay = 2 ** (attempt - 1) + random.uniform(0, 0.5)
    if cancel_event is not None:
        if cancel_event.wait(delay):
            raise CancelledError("surveillance sweep cancelled")
    else:
        time.sleep(delay)


def graphql_url_for(github_url: str) -> str:
    """Return the GraphQL API endpoint for a given GitHub base URL.

    github.com uses a different hostname for its API (api.github.com),
    while GitHub Enterprise Server exposes the API at <host>/api/graphql.
    """
    url = github_url.rstrip("/")
    if url == "https://github.com":
        return "https://api.github.com/graphql"
    return f"{url}/api/graphql"


def make_github_graphql_request(
    query,
    github_url: str = DEFAULT_GITHUB_URL,
    *,
    cancel_event=None,
):
    """POST a GraphQL query with bounded retries and error reporting.

    Args:
        query: GraphQL query string to execute.
        github_url: GitHub or GitHub Enterprise base URL.
        cancel_event: Optional event used to stop retries after a concurrent
            range fails.

    Returns:
        dict: Parsed GitHub GraphQL response.

    Raises:
        GitHubGraphQLRateLimitError: If GitHub reports ``RATE_LIMITED``.
        GitHubGraphQLResourceLimitError: If GitHub reports only
            ``RESOURCE_LIMITS_EXCEEDED`` fatal errors.
        GitHubGraphQLError: If GitHub returns other fatal GraphQL errors.
        requests.exceptions.RequestException: If an HTTP or transport failure
            remains after retries.
        CancelledError: If another concurrent range has already failed.
    """
    headers = {
        "Authorization": f"bearer {SECRET_GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    graphql_url = graphql_url_for(github_url)
    for attempt in range(_MAX_RETRIES + 1):
        _wait_before_retry(attempt, cancel_event)
        try:
            request_start = time.monotonic()
            _record_graphql_call()
            response = requests.post(
                graphql_url,
                json={"query": query},
                headers=headers,
                timeout=_REQUEST_TIMEOUT,
            )
            elapsed_ms = int((time.monotonic() - request_start) * 1000)
            if response.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES:
                logger.warning(
                    "GraphQL request status=%d elapsed_ms=%d attempt=%d retrying",
                    response.status_code,
                    elapsed_ms,
                    attempt + 1,
                )
                continue

            response.raise_for_status()
            data = response.json()
            raw_errors = data.get("errors") or []
            errors = raw_errors if isinstance(raw_errors, list) else [raw_errors]
            fatal_errors = [
                error
                for error in errors
                if not (isinstance(error, dict) and error.get("type") == "NOT_FOUND")
            ]
            if fatal_errors:
                summary = _summarize_graphql_errors(fatal_errors)
                logger.warning(
                    "GraphQL request failed status=%d elapsed_ms=%d "
                    "error_count=%d errors=%s",
                    response.status_code,
                    elapsed_ms,
                    len(fatal_errors),
                    summary,
                )
                error_types = {
                    error.get("type") if isinstance(error, dict) else None
                    for error in fatal_errors
                }
                if error_types == {"RATE_LIMITED"}:
                    raise GitHubGraphQLRateLimitError(
                        fatal_errors,
                        reset_at=_rate_limit_reset_at(response),
                    )
                if error_types == {"RESOURCE_LIMITS_EXCEEDED"}:
                    raise GitHubGraphQLResourceLimitError(fatal_errors)
                raise GitHubGraphQLError(fatal_errors)

            for error in errors[:_MAX_STORED_GRAPHQL_ERRORS]:
                message = (
                    error.get("message", error) if isinstance(error, dict) else error
                )
                logger.warning("operative not found: %s", _bounded_message(message))
            if len(errors) > _MAX_STORED_GRAPHQL_ERRORS:
                logger.warning(
                    "%d additional operative-not-found error(s) omitted",
                    len(errors) - _MAX_STORED_GRAPHQL_ERRORS,
                )
            return data
        except (
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as exc:
            logger.warning(
                "GraphQL transport failure url=%s attempt=%d error=%s",
                graphql_url,
                attempt + 1,
                _bounded_message(exc),
            )
            if attempt == _MAX_RETRIES:
                raise


def get_graphql_rate_limit(github_url: str = DEFAULT_GITHUB_URL):
    """Return GitHub's current GraphQL rate-limit status when available.

    Args:
        github_url: GitHub or GitHub Enterprise base URL.

    Returns:
        dict | None: The GraphQL ``rateLimit`` node, or ``None`` when the
        endpoint does not expose it or the diagnostics request fails.
    """
    query = """
    query {
      rateLimit {
        cost
        remaining
        resetAt
        used
      }
    }
    """
    try:
        response = make_github_graphql_request(query, github_url)
    except (GitHubGraphQLError, requests.exceptions.RequestException) as exc:
        logger.debug("GraphQL rate-limit diagnostics unavailable: %s", exc)
        return None

    data = response.get("data")
    if not isinstance(data, dict):
        return None
    rate_limit = data.get("rateLimit")
    return rate_limit if isinstance(rate_limit, dict) else None


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


def _fetch_year(users, label, from_iso, to_iso, github_url, cancel_event=None):
    """Fetch contributions for all users for a single year range.

    Args:
        users: GitHub usernames included in the query.
        label: Display label for the date range.
        from_iso: Inclusive range start in ISO format.
        to_iso: Inclusive range end in ISO format.
        github_url: GitHub or GitHub Enterprise base URL.
        cancel_event: Optional signal used to stop concurrent retries.

    Returns:
        tuple: Range label and its GraphQL data mapping.
    """
    logger.debug(
        "fetching year=%s users=%s from=%s to=%s", label, users, from_iso, to_iso
    )
    query = build_contributions_query(users, from_iso, to_iso)
    data = make_github_graphql_request(
        query,
        github_url,
        cancel_event=cancel_event,
    )
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

    cancel_event = threading.Event()
    executor = ThreadPoolExecutor()
    futures = set()
    try:
        for label, from_iso, to_iso in ranges:
            futures.add(
                executor.submit(
                    _fetch_year,
                    users,
                    label,
                    from_iso,
                    to_iso,
                    github_url,
                    cancel_event,
                )
            )

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
    finally:
        cancel_event.set()
        for pending_future in futures:
            pending_future.cancel()
        # Active HTTP calls cannot be interrupted, but the event prevents each
        # worker from starting another retry after its current request returns.
        executor.shutdown(wait=True, cancel_futures=True)

    not_found = {u for u, c in null_counts.items() if c == total}
    return result, not_found
