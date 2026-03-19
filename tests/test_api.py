from datetime import date, datetime
from unittest.mock import patch

import pytest
import requests

from ghsnitch.api import (
    build_contributions_query,
    fetch_contributions,
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
        result = fetch_contributions(["alice"], 1)

    assert result["alice"][current_year] == 150
    assert result["alice"][prior_year] == 150


def test_fetch_contributions_null_user_returns_zero(requests_mock):
    current_year = str(date.today().year)

    requests_mock.post(
        "https://api.github.com/graphql",
        json={"data": {"user_ghost": None}},
    )

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        result = fetch_contributions(["ghost"], 0)

    assert result["ghost"][current_year] == 0


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
        result = fetch_contributions(["alice"], 0, "https://github.example.com")

    assert result["alice"][current_year] == 99


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


def test_make_github_graphql_request_raises_on_http_error(requests_mock):
    requests_mock.post("https://api.github.com/graphql", status_code=401)

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "bad-token"):
        with pytest.raises(requests.exceptions.HTTPError):
            make_github_graphql_request("{ viewer { login } }")


def test_make_github_graphql_request_raises_on_graphql_errors(requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql",
        json={"errors": [{"message": "Not found"}]},
    )

    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
        with pytest.raises(ValueError, match="GraphQL errors"):
            make_github_graphql_request("{ viewer { login } }")
