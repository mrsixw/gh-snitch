from datetime import date, datetime
from unittest.mock import patch

import pytest
import requests

from ghsnitch.api import (
    build_contributions_query,
    current_year_fraction,
    fetch_contributions,
    get_custom_range,
    get_period_range,
    get_rolling_month_ranges,
    get_rolling_week_ranges,
    get_year_ranges,
    graphql_url_for,
    make_github_graphql_request,
)


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
        json={
            "data": {
                "user_alice": {
                    "login": "alice",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 7}
                    },
                }
            }
        },
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
    assert "user_alice" in query
    assert "user_bob" in query
    assert "contributionCalendar" in query
    assert "totalContributions" in query


def test_build_contributions_query_handles_hyphen_in_username():
    query = build_contributions_query(
        ["my-user"], "2025-01-01T00:00:00+00:00", "2025-12-31T23:59:59+00:00"
    )
    assert "user_my_user" in query


def test_fetch_contributions_parses_response(requests_mock):
    current_year = str(date.today().year)
    prior_year = str(date.today().year - 1)

    def graphql_handler(request, context):
        return {
            "data": {
                "user_alice": {
                    "login": "alice",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 150}
                    },
                }
            }
        }

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
        json={"data": {"user_ghost": None}},
    )

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        result, not_found = fetch_contributions(["ghost"], 0)

    assert result["ghost"][current_year] == 0
    assert "ghost" in not_found


def test_fetch_contributions_uses_enterprise_url(requests_mock):
    current_year = str(date.today().year)

    requests_mock.post(
        "https://github.example.com/api/graphql",
        json={
            "data": {
                "user_alice": {
                    "login": "alice",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 99}
                    },
                }
            }
        },
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
        json={
            "data": {
                "user_alice": {
                    "login": "alice",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 1}
                    },
                }
            }
        },
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
        result, not_found = fetch_contributions(["ghost"], 0)

    assert result["ghost"][current_year] == 0
    assert "ghost" in not_found


def test_make_github_graphql_request_raises_on_non_not_found_errors(requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql",
        json={"errors": [{"type": "FORBIDDEN", "message": "Access denied"}]},
    )

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        with pytest.raises(ValueError, match="GraphQL errors"):
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
        with pytest.raises(ValueError, match="GraphQL errors"):
            make_github_graphql_request("{ viewer { login } }")
