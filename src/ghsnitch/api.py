import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

import requests

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
        raise ValueError(f"GraphQL errors: {data['errors']}")
    return data


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


def build_contributions_query(users, from_iso, to_iso):
    """Build a GraphQL query with aliases for each user."""
    aliases = []
    for username in users:
        alias = f"user_{username.replace('-', '_').replace('.', '_')}"
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
    query = build_contributions_query(users, from_iso, to_iso)
    data = make_github_graphql_request(query, github_url)
    return label, data.get("data", {})


def fetch_contributions(
    users, years, github_url: str = DEFAULT_GITHUB_URL, on_progress=None
):
    """Fetch contribution counts for all users across year ranges.

    Requests are dispatched concurrently — one per year range.
    Returns dict[username][label] = int.
    on_progress, if provided, is called with (completed, total) after each year.
    """
    year_ranges = get_year_ranges(years)
    total = len(year_ranges)
    result = {username: {} for username in users}

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(_fetch_year, users, label, from_iso, to_iso, github_url)
            for label, from_iso, to_iso in year_ranges
        }

        for completed, future in enumerate(as_completed(futures), start=1):
            label, response_data = future.result()

            for username in users:
                alias = f"user_{username.replace('-', '_').replace('.', '_')}"
                user_data = response_data.get(alias)
                if user_data is None:
                    result[username][label] = 0
                else:
                    count = (
                        user_data.get("contributionsCollection", {})
                        .get("contributionCalendar", {})
                        .get("totalContributions", 0)
                    )
                    result[username][label] = count

            if on_progress is not None:
                on_progress(completed, total)

    return result
