import re
import threading
from concurrent.futures import CancelledError, ThreadPoolExecutor
from datetime import date, datetime
from unittest.mock import patch

import pytest
import requests

from ghsnitch.api import (
    GitHubGraphQLError,
    GitHubGraphQLRateLimitError,
    GitHubGraphQLResourceLimitError,
    _fetch_year,
    _resolve_github_token,
    build_contributions_query,
    configure_api_stats,
    current_year_fraction,
    fetch_contributions,
    get_api_stats,
    get_custom_range,
    get_graphql_rate_limit,
    get_period_range,
    get_rolling_month_ranges,
    get_rolling_week_ranges,
    get_year_ranges,
    graphql_url_for,
    make_github_graphql_request,
)


def _graphql_response(*users, errors=None):
    """Build a mock GraphQL response dict matching the current alias scheme.

    Pass (login, total_contributions) pairs; use None for count to simulate
    a null/not-found user:
        _graphql_response(("alice", 50), ("bob", 30))
        _graphql_response(("ghost", None), errors=[{...}])
    """
    data = {}
    for i, (login, count) in enumerate(users):
        if count is None:
            data[f"user_{i}"] = None
        else:
            data[f"user_{i}"] = {
                "login": login,
                "contributionsCollection": {
                    "contributionCalendar": {"totalContributions": count}
                },
            }
    response = {"data": data}
    if errors is not None:
        response["errors"] = errors
    return response


def _query_logins(request):
    """Return operative logins from a mocked GraphQL request in alias order."""
    return re.findall(r'user\(login: "([^"]+)"\)', request.json()["query"])


def test_resolve_github_token_prefers_gh_token(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "gh-token")
    monkeypatch.setenv("GITHUB_TOKEN", "github-token")
    assert _resolve_github_token() == "gh-token"


def test_resolve_github_token_falls_back_to_github_token(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "github-token")
    assert _resolve_github_token() == "github-token"


def test_resolve_github_token_none_when_unset(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert _resolve_github_token() is None


def test_graphql_url_for_github_com():
    assert graphql_url_for("https://github.com") == "https://api.github.com/graphql"


def test_graphql_url_for_github_com_trailing_slash():
    assert graphql_url_for("https://github.com/") == "https://api.github.com/graphql"


def test_graphql_url_for_enterprise():
    assert (
        graphql_url_for("https://github.example.com")
        == "https://github.example.com/api/graphql"
    )


def test_graphql_url_for_enterprise_trailing_slash():
    assert (
        graphql_url_for("https://github.example.com/")
        == "https://github.example.com/api/graphql"
    )


def test_get_period_range_month():
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        label, from_iso, to_iso = get_period_range("month")
    assert label == "This Month"
    from_dt = datetime.fromisoformat(from_iso)
    to_dt = datetime.fromisoformat(to_iso)
    assert from_dt.month == 4 and from_dt.day == 1
    assert to_dt.month == 4 and to_dt.day == 15


def test_get_period_range_week():
    # 2026-04-15 is a Wednesday; Monday is 2026-04-13
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        label, from_iso, to_iso = get_period_range("week")
    assert label == "This Week"
    from_dt = datetime.fromisoformat(from_iso)
    to_dt = datetime.fromisoformat(to_iso)
    assert from_dt.day == 13  # Monday
    assert to_dt.day == 15  # today


def test_get_period_range_year():
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        label, from_iso, to_iso = get_period_range("year")
    assert label == "This Year"
    from_dt = datetime.fromisoformat(from_iso)
    to_dt = datetime.fromisoformat(to_iso)
    assert from_dt.month == 1 and from_dt.day == 1
    assert to_dt.month == 4 and to_dt.day == 15


def test_get_period_range_invalid():
    with pytest.raises(ValueError, match="Unknown period"):
        get_period_range("decade")


# --- get_rolling_month_ranges ---


def test_get_rolling_month_ranges_count():
    ranges = get_rolling_month_ranges(4)
    assert len(ranges) == 4


def test_get_rolling_month_ranges_labels_descending():
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        ranges = get_rolling_month_ranges(3)
    labels = [r[0] for r in ranges]
    assert labels == ["Apr 2026", "Mar 2026", "Feb 2026"]


def test_get_rolling_month_ranges_current_month_ends_today():
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        ranges = get_rolling_month_ranges(1)
    _, _, to_iso = ranges[0]
    to_dt = datetime.fromisoformat(to_iso)
    assert to_dt.day == 15


def test_get_rolling_month_ranges_prior_month_ends_on_last_day():
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        ranges = get_rolling_month_ranges(2)
    _, _, to_iso = ranges[1]  # March
    to_dt = datetime.fromisoformat(to_iso)
    assert to_dt.day == 31  # March has 31 days


def test_get_rolling_month_ranges_crosses_year_boundary():
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2026, 2, 10)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        ranges = get_rolling_month_ranges(3)
    labels = [r[0] for r in ranges]
    assert labels == ["Feb 2026", "Jan 2026", "Dec 2025"]


# --- get_rolling_week_ranges ---


def test_get_rolling_week_ranges_count():
    ranges = get_rolling_week_ranges(5)
    assert len(ranges) == 5


def test_get_rolling_week_ranges_labels_descending():
    # 2026-04-15 is Wednesday; date(2026, 4, 15).isocalendar() == (2026, 16, 3)
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        ranges = get_rolling_week_ranges(3)
    labels = [r[0] for r in ranges]
    assert labels == ["2026-W16", "2026-W15", "2026-W14"]


def test_get_rolling_week_ranges_current_week_ends_today():
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 15)  # Wednesday
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        ranges = get_rolling_week_ranges(1)
    _, _, to_iso = ranges[0]
    to_dt = datetime.fromisoformat(to_iso)
    assert to_dt.day == 15


def test_get_rolling_week_ranges_prior_week_ends_sunday():
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2026, 4, 15)  # Wed W15
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        ranges = get_rolling_week_ranges(2)
    _, _, to_iso = ranges[1]  # prior week W14
    to_dt = datetime.fromisoformat(to_iso)
    assert to_dt.weekday() == 6  # Sunday


# --- get_custom_range ---


def test_get_custom_range_since_only():
    from datetime import timezone as tz

    today = date.today()
    label, from_iso, to_iso = get_custom_range("2025-01-01")
    assert label == "Since 2025-01-01"
    expected = datetime(2025, 1, 1, 0, 0, 0, tzinfo=tz.utc)
    assert datetime.fromisoformat(from_iso) == expected
    assert datetime.fromisoformat(to_iso).date() == today


def test_get_custom_range_since_and_until():
    label, from_iso, to_iso = get_custom_range("2025-01-01", "2025-03-31")
    assert label == "2025-01-01–2025-03-31"
    assert datetime.fromisoformat(from_iso).month == 1
    assert datetime.fromisoformat(to_iso).month == 3


def test_get_custom_range_invalid_since():
    with pytest.raises(ValueError, match="Invalid date"):
        get_custom_range("not-a-date")


def test_get_custom_range_invalid_until():
    with pytest.raises(ValueError, match="Invalid date"):
        get_custom_range("2025-01-01", "bad")


def test_get_custom_range_since_after_until():
    with pytest.raises(ValueError, match="must not be after"):
        get_custom_range("2025-06-01", "2025-01-01")


def test_fetch_contributions_with_period(requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("alice", 7)),
    )

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        result, not_found = fetch_contributions(["alice"], years=3, period="week")

    assert result["alice"]["This Week"] == 7
    assert not_found == set()


def test_get_year_ranges_structure():
    ranges = get_year_ranges(2)
    assert len(ranges) == 3  # current year + 2 prior
    labels = [r[0] for r in ranges]
    current_year = str(date.today().year)
    assert labels[0] == current_year
    assert labels[1] == str(date.today().year - 1)
    assert labels[2] == str(date.today().year - 2)


def test_get_year_ranges_current_year_starts_jan_1():
    ranges = get_year_ranges(1)
    label, from_iso, to_iso = ranges[0]
    from_dt = datetime.fromisoformat(from_iso)
    assert from_dt.month == 1
    assert from_dt.day == 1


def test_get_year_ranges_prior_year_is_full_year():
    ranges = get_year_ranges(1)
    label, from_iso, to_iso = ranges[1]
    from_dt = datetime.fromisoformat(from_iso)
    to_dt = datetime.fromisoformat(to_iso)
    assert from_dt.month == 1
    assert from_dt.day == 1
    assert to_dt.month == 12
    assert to_dt.day == 31


def test_build_contributions_query_contains_aliases():
    query = build_contributions_query(
        ["alice", "bob"], "2025-01-01T00:00:00+00:00", "2025-12-31T23:59:59+00:00"
    )
    assert "user_0" in query
    assert "user_1" in query
    assert "contributionCalendar" in query
    assert "totalContributions" in query


def test_build_contributions_query_handles_hyphen_in_username():
    query = build_contributions_query(
        ["my-user"], "2025-01-01T00:00:00+00:00", "2025-12-31T23:59:59+00:00"
    )
    assert "user_0" in query
    assert 'login: "my-user"' in query


def test_build_contributions_query_no_alias_collision_for_similar_usernames():
    """agent-007 and agent_007 must not produce the same GraphQL alias."""
    query = build_contributions_query(
        ["agent-007", "agent_007"],
        "2025-01-01T00:00:00+00:00",
        "2025-12-31T23:59:59+00:00",
    )
    assert 'user_0: user(login: "agent-007")' in query
    assert 'user_1: user(login: "agent_007")' in query


def test_fetch_contributions_parses_response(requests_mock):
    current_year = str(date.today().year)
    prior_year = str(date.today().year - 1)

    def graphql_handler(request, context):
        return _graphql_response(("alice", 150))

    requests_mock.post("https://api.github.com/graphql", json=graphql_handler)

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        result, not_found = fetch_contributions(["alice"], 1)

    assert result["alice"][current_year] == 150
    assert result["alice"][prior_year] == 150
    assert not_found == set()


def test_fetch_contributions_null_user_returns_zero(requests_mock):
    current_year = str(date.today().year)

    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("ghost", None)),
    )

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        result, not_found = fetch_contributions(["ghost"], 0)

    assert result["ghost"][current_year] == 0
    assert "ghost" in not_found


def test_fetch_contributions_uses_enterprise_url(requests_mock):
    current_year = str(date.today().year)

    requests_mock.post(
        "https://github.example.com/api/graphql",
        json=_graphql_response(("alice", 99)),
    )

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        result, not_found = fetch_contributions(
            ["alice"], 0, "https://github.example.com"
        )

    assert result["alice"][current_year] == 99
    assert not_found == set()


def test_fetch_contributions_calls_on_progress(requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("alice", 1)),
    )

    calls = []
    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        fetch_contributions(["alice"], 1, on_progress=lambda c, t: calls.append((c, t)))

    # years=1 → 2 ranges (current + 1 prior), progress called once per range
    assert len(calls) == 2
    assert calls[0] == (1, 2)
    assert calls[1] == (2, 2)


def test_fetch_contributions_not_found_user_via_graphql_error(requests_mock):
    """NOT_FOUND GraphQL errors should not crash; affected user appears in not_found."""
    current_year = str(date.today().year)

    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(
            ("ghost", None),
            errors=[
                {
                    "type": "NOT_FOUND",
                    "path": ["user_0"],
                    "message": "Could not resolve to a User with the login of 'ghost'.",
                }
            ],
        ),
    )

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        result, not_found = fetch_contributions(["ghost"], 0)

    assert result["ghost"][current_year] == 0
    assert "ghost" in not_found


def test_fetch_contributions_bounds_operative_batch_size(requests_mock):
    """A range should split large cohorts into batches of at most ten users."""
    users = [f"operative-{index}" for index in range(23)]
    batch_sizes = []

    def graphql_handler(request, _context):
        logins = _query_logins(request)
        batch_sizes.append(len(logins))
        return _graphql_response(
            *((login, int(login.rsplit("-", 1)[1])) for login in logins)
        )

    requests_mock.post("https://api.github.com/graphql", json=graphql_handler)
    ranges = [("Range", "2026-01-01T00:00:00+00:00", "2026-01-31T23:59:59+00:00")]

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        result, not_found = fetch_contributions(users, 0, year_ranges=ranges)

    assert batch_sizes == [10, 10, 3]
    assert result["operative-22"]["Range"] == 22
    assert not_found == set()


def test_fetch_contributions_reduces_and_retains_resource_limited_batch(
    requests_mock,
):
    """A rejected batch should halve once and retain the successful size."""
    users = [f"operative-{index}" for index in range(12)]
    batch_sizes = []
    progress = []

    def graphql_handler(request, _context):
        logins = _query_logins(request)
        batch_sizes.append(len(logins))
        if len(logins) == 10:
            return {
                "data": _graphql_response(*((login, 999) for login in logins))["data"],
                "errors": [
                    {
                        "type": "RESOURCE_LIMITS_EXCEEDED",
                        "message": "Resource limits for this query exceeded.",
                    }
                ],
            }
        return _graphql_response(
            *((login, int(login.rsplit("-", 1)[1])) for login in logins)
        )

    requests_mock.post("https://api.github.com/graphql", json=graphql_handler)
    ranges = [("Range", "2026-01-01T00:00:00+00:00", "2026-01-31T23:59:59+00:00")]

    configure_api_stats(True)
    try:
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result, not_found = fetch_contributions(
                users,
                0,
                on_progress=lambda completed, total: progress.append(
                    (completed, total)
                ),
                year_ranges=ranges,
            )

        assert get_api_stats() == {"graphql_calls": 4}
    finally:
        configure_api_stats(False)

    assert batch_sizes == [10, 5, 5, 2]
    assert result["operative-0"]["Range"] == 0
    assert result["operative-11"]["Range"] == 11
    assert not_found == set()
    assert progress == [(1, 1)]


def test_fetch_contributions_propagates_resource_limit_at_singleton(
    requests_mock,
):
    """Adaptive batching should stop when GitHub rejects one operative."""
    batch_sizes = []

    def graphql_handler(request, _context):
        logins = _query_logins(request)
        batch_sizes.append(len(logins))
        return {
            "errors": [
                {
                    "type": "RESOURCE_LIMITS_EXCEEDED",
                    "message": "Resource limits for this query exceeded.",
                }
            ]
        }

    requests_mock.post("https://api.github.com/graphql", json=graphql_handler)
    users = [f"operative-{index}" for index in range(10)]
    ranges = [("Range", "2026-01-01T00:00:00+00:00", "2026-01-31T23:59:59+00:00")]

    with (
        patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
        pytest.raises(GitHubGraphQLResourceLimitError),
    ):
        fetch_contributions(users, 0, year_ranges=ranges)

    assert batch_sizes == [10, 5, 2, 1]


def test_fetch_contributions_does_not_adapt_mixed_fatal_errors(requests_mock):
    """Only pure resource-limit failures should trigger smaller batches."""
    batch_sizes = []

    def graphql_handler(request, _context):
        batch_sizes.append(len(_query_logins(request)))
        return {
            "errors": [
                {"type": "FORBIDDEN", "message": "Access denied."},
                {
                    "type": "RESOURCE_LIMITS_EXCEEDED",
                    "message": "Resource limits for this query exceeded.",
                },
            ]
        }

    requests_mock.post("https://api.github.com/graphql", json=graphql_handler)
    ranges = [("Range", "2026-01-01T00:00:00+00:00", "2026-01-31T23:59:59+00:00")]

    with (
        patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
        pytest.raises(GitHubGraphQLError) as exc_info,
    ):
        fetch_contributions(["alice", "bob", "carol"], 0, year_ranges=ranges)

    assert type(exc_info.value) is GitHubGraphQLError
    assert batch_sizes == [3]


def test_fetch_contributions_preserves_not_found_during_resource_recovery(
    requests_mock,
):
    """Benign NOT_FOUND errors should survive adaptive resource recovery."""
    batch_sizes = []

    def graphql_handler(request, _context):
        logins = _query_logins(request)
        batch_sizes.append(len(logins))
        if len(logins) > 1:
            return {
                "data": _graphql_response(*((login, 999) for login in logins))["data"],
                "errors": [
                    {
                        "type": "NOT_FOUND",
                        "message": "Could not resolve an operative.",
                    },
                    {
                        "type": "RESOURCE_LIMITS_EXCEEDED",
                        "message": "Resource limits for this query exceeded.",
                    },
                ],
            }
        login = logins[0]
        if login == "ghost":
            return _graphql_response(
                (login, None),
                errors=[
                    {
                        "type": "NOT_FOUND",
                        "message": "Could not resolve an operative.",
                    }
                ],
            )
        return _graphql_response((login, 7))

    requests_mock.post("https://api.github.com/graphql", json=graphql_handler)
    ranges = [("Range", "2026-01-01T00:00:00+00:00", "2026-01-31T23:59:59+00:00")]

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        result, not_found = fetch_contributions(
            ["alice", "ghost", "bob"], 0, year_ranges=ranges
        )

    assert batch_sizes == [3, 1, 1, 1]
    assert result["alice"]["Range"] == 7
    assert result["ghost"]["Range"] == 0
    assert result["bob"]["Range"] == 7
    assert not_found == {"ghost"}


def test_fetch_contributions_caps_concurrent_ranges():
    """The range executor should never exceed the internal worker cap."""
    ranges = [
        (
            f"Range {index}",
            "2026-01-01T00:00:00+00:00",
            "2026-01-31T23:59:59+00:00",
        )
        for index in range(6)
    ]

    def fake_fetch(_users, label, _from_iso, _to_iso, _github_url, _cancel_event):
        return label, {"alice": 1}, set()

    with (
        patch("ghsnitch.api._fetch_year", side_effect=fake_fetch),
        patch(
            "ghsnitch.api.ThreadPoolExecutor", wraps=ThreadPoolExecutor
        ) as executor_class,
    ):
        result, not_found = fetch_contributions(["alice"], 0, year_ranges=ranges)

    executor_class.assert_called_once_with(max_workers=4)
    assert len(result["alice"]) == 6
    assert not_found == set()


def test_fetch_year_honours_cancellation_between_batches(requests_mock):
    """Cancellation after one batch should prevent the next GraphQL request."""
    cancel_event = threading.Event()

    def graphql_handler(request, _context):
        logins = _query_logins(request)
        cancel_event.set()
        return _graphql_response(*((login, 1) for login in logins))

    adapter = requests_mock.post("https://api.github.com/graphql", json=graphql_handler)
    users = [f"operative-{index}" for index in range(12)]

    with (
        patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
        pytest.raises(CancelledError, match="surveillance sweep cancelled"),
    ):
        _fetch_year(
            users,
            "Range",
            "2026-01-01T00:00:00+00:00",
            "2026-01-31T23:59:59+00:00",
            "https://github.com",
            cancel_event,
        )

    assert adapter.call_count == 1


def test_make_github_graphql_request_raises_on_non_not_found_errors(requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql",
        json={"errors": [{"type": "FORBIDDEN", "message": "Access denied"}]},
    )

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        with pytest.raises(GitHubGraphQLError, match="GraphQL request failed"):
            make_github_graphql_request("{ viewer { login } }")


def test_make_github_graphql_request_tolerates_not_found_errors(requests_mock):
    """NOT_FOUND errors should not raise; partial data is returned."""
    requests_mock.post(
        "https://api.github.com/graphql",
        json={
            "data": {"user_ghost": None},
            "errors": [
                {
                    "type": "NOT_FOUND",
                    "path": ["user_ghost"],
                    "message": "Could not resolve to a User with the login of 'ghost'.",
                }
            ],
        },
    )

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        data = make_github_graphql_request("{ user_ghost { login } }")

    assert data["data"]["user_ghost"] is None


def test_current_year_fraction_jan_1():
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2025, 1, 1)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        fraction = current_year_fraction()
    assert fraction == pytest.approx(1 / 365)


def test_current_year_fraction_dec_31():
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2025, 12, 31)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        fraction = current_year_fraction()
    assert fraction == pytest.approx(1.0)


def test_current_year_fraction_leap_year():
    # 2024 is a leap year (366 days); Jan 1 → 1/366
    with patch("ghsnitch.api.date") as mock_date:
        mock_date.today.return_value = date(2024, 1, 1)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        fraction = current_year_fraction()
    assert fraction == pytest.approx(1 / 366)


def test_make_github_graphql_request_raises_on_http_error(requests_mock):
    requests_mock.post("https://api.github.com/graphql", status_code=401)

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "bad-token"):
        with pytest.raises(requests.exceptions.HTTPError):
            make_github_graphql_request("{ viewer { login } }")


def test_make_github_graphql_request_raises_on_graphql_errors(requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql",
        json={"errors": [{"type": "INTERNAL", "message": "Something went wrong"}]},
    )

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        with pytest.raises(GitHubGraphQLError, match="GraphQL request failed"):
            make_github_graphql_request("{ viewer { login } }")


def test_make_github_graphql_request_retries_transient_status_then_succeeds(
    requests_mock,
):
    adapter = requests_mock.post(
        "https://api.github.com/graphql",
        [
            {"status_code": 503},
            {"json": {"data": {"viewer": {"login": "alice"}}}},
        ],
    )

    with (
        patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
        patch("ghsnitch.api.random.uniform", return_value=0),
        patch("ghsnitch.api.time.sleep") as sleep,
    ):
        data = make_github_graphql_request("{ viewer { login } }")

    assert data["data"]["viewer"]["login"] == "alice"
    assert adapter.call_count == 2
    sleep.assert_called_once_with(1)


def test_make_github_graphql_request_retries_connection_error_then_succeeds(
    requests_mock,
):
    adapter = requests_mock.post(
        "https://api.github.com/graphql",
        [
            {"exc": requests.exceptions.ConnectionError("signal interrupted")},
            {"json": {"data": {"viewer": {"login": "alice"}}}},
        ],
    )

    with (
        patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
        patch("ghsnitch.api.random.uniform", return_value=0),
        patch("ghsnitch.api.time.sleep"),
    ):
        data = make_github_graphql_request("{ viewer { login } }")

    assert data["data"]["viewer"]["login"] == "alice"
    assert adapter.call_count == 2


def test_make_github_graphql_request_exhausts_three_retries(requests_mock):
    adapter = requests_mock.post(
        "https://api.github.com/graphql",
        status_code=503,
    )

    with (
        patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
        patch("ghsnitch.api.random.uniform", return_value=0),
        patch("ghsnitch.api.time.sleep") as sleep,
        pytest.raises(requests.exceptions.HTTPError),
    ):
        make_github_graphql_request("{ viewer { login } }")

    assert adapter.call_count == 4
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2, 4]


def test_api_stats_count_every_graphql_post_attempt(requests_mock):
    adapter = requests_mock.post(
        "https://api.github.com/graphql",
        [
            {"status_code": 503},
            {"json": {"data": {"viewer": {"login": "alice"}}}},
        ],
    )

    configure_api_stats(True)
    try:
        with (
            patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
            patch("ghsnitch.api._wait_before_retry"),
        ):
            make_github_graphql_request("{ viewer { login } }")

        assert adapter.call_count == 2
        assert get_api_stats() == {"graphql_calls": 2}
    finally:
        configure_api_stats(False)


def test_get_graphql_rate_limit_returns_endpoint_data():
    rate_limit = {
        "cost": 1,
        "remaining": 4987,
        "resetAt": "2026-07-17T13:00:00Z",
        "used": 13,
    }
    with patch(
        "ghsnitch.api.make_github_graphql_request",
        return_value={"data": {"rateLimit": rate_limit}},
    ) as request:
        result = get_graphql_rate_limit("https://github.example.com")

    assert result == rate_limit
    assert request.call_args.args[1] == "https://github.example.com"
    assert "rateLimit" in request.call_args.args[0]


def test_get_graphql_rate_limit_returns_none_when_diagnostics_fail():
    with patch(
        "ghsnitch.api.make_github_graphql_request",
        side_effect=requests.exceptions.ConnectionError("signal lost"),
    ):
        result = get_graphql_rate_limit()

    assert result is None


def test_make_github_graphql_request_maps_rate_limit_with_reset(requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql",
        json={"errors": [{"type": "RATE_LIMITED", "message": "Slow down"}]},
        headers={"X-RateLimit-Reset": "1750000000"},
    )

    with (
        patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
        pytest.raises(GitHubGraphQLRateLimitError) as exc_info,
    ):
        make_github_graphql_request("{ viewer { login } }")

    assert exc_info.value.error_count == 1
    assert exc_info.value.reset_at is not None
    assert exc_info.value.reset_at.endswith("UTC")


def test_make_github_graphql_request_maps_resource_limit_from_fatal_subset(
    requests_mock,
):
    requests_mock.post(
        "https://api.github.com/graphql",
        json={
            "data": {"user_0": None},
            "errors": [
                {"type": "NOT_FOUND", "message": "Operative missing"},
                {
                    "type": "RESOURCE_LIMITS_EXCEEDED",
                    "message": "Resource limits for this query exceeded.",
                },
            ],
        },
    )

    with (
        patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
        pytest.raises(GitHubGraphQLResourceLimitError) as exc_info,
    ):
        make_github_graphql_request("{ user_0 { login } }")

    assert exc_info.value.error_count == 1
    assert "NOT_FOUND" not in exc_info.value.summary


def test_make_github_graphql_request_bounds_repeated_resource_errors(
    requests_mock, caplog
):
    errors = [
        {
            "type": "RESOURCE_LIMITS_EXCEEDED",
            "path": ["user_0", "contributionsCollection", index],
            "message": "Resource limits for this query exceeded.",
        }
        for index in range(500)
    ]
    requests_mock.post(
        "https://api.github.com/graphql",
        json={"data": {"user_0": None}, "errors": errors},
    )

    with (
        patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
        caplog.at_level("WARNING", logger="ghsnitch.api"),
        pytest.raises(GitHubGraphQLResourceLimitError) as exc_info,
    ):
        make_github_graphql_request("{ user_0 { login } }")

    error = exc_info.value
    assert error.error_count == 500
    assert len(error.errors) == 10
    assert "RESOURCE_LIMITS_EXCEEDED=500" in str(error)
    assert len(str(error)) < 250
    assert caplog.text.count("Resource limits for this query exceeded") == 1
    assert len(caplog.text) < 600


def test_make_github_graphql_request_keeps_mixed_fatal_errors_generic(requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql",
        json={
            "errors": [
                {"type": "RATE_LIMITED", "message": "Slow down"},
                {
                    "type": "RESOURCE_LIMITS_EXCEEDED",
                    "message": "Query too broad",
                },
            ]
        },
    )

    with (
        patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
        pytest.raises(GitHubGraphQLError) as exc_info,
    ):
        make_github_graphql_request("{ viewer { login } }")

    assert type(exc_info.value) is GitHubGraphQLError
    assert "RATE_LIMITED=1" in exc_info.value.summary
    assert "RESOURCE_LIMITS_EXCEEDED=1" in exc_info.value.summary


def test_make_github_graphql_request_honours_cancelled_sweep(requests_mock):
    adapter = requests_mock.post(
        "https://api.github.com/graphql",
        json={"data": {"viewer": {"login": "alice"}}},
    )
    cancel_event = threading.Event()
    cancel_event.set()

    with (
        patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"),
        pytest.raises(CancelledError, match="surveillance sweep cancelled"),
    ):
        make_github_graphql_request(
            "{ viewer { login } }",
            cancel_event=cancel_event,
        )

    assert adapter.call_count == 0
