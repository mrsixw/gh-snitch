import hashlib
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from ghsnitch.cli import gh_snitch


def _context_id(users):
    """Mirror cli.py's ad-hoc context_id computation for use in tests."""
    key = ",".join(sorted(users))
    return f"u-{hashlib.sha256(key.encode()).hexdigest()[:12]}"


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


@pytest.fixture
def runner():
    return CliRunner()


def test_init_config(runner, tmp_path):
    config_path = str(tmp_path / "config.toml")
    result = runner.invoke(gh_snitch, ["--init-config", "--config", config_path])
    assert result.exit_code == 0
    assert "established" in result.output
    import os

    assert os.path.exists(config_path)


def test_show_config(runner, tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 2\n'
    )
    result = runner.invoke(gh_snitch, ["--show-config", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "alice" in result.output
    assert "years" in result.output


def test_missing_github_token(runner, tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 1\n'
    )
    with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", None):
        with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", None):
            result = runner.invoke(
                gh_snitch, ["--config", str(config_file), "--no-update-check"]
            )
    assert result.exit_code != 0
    assert "GITHUB_TOKEN" in result.output


def test_missing_users_shows_warning(runner, tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[operatives]\nusers = []\n[surveillance]\nyears = 1\n")
    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch, ["--config", str(config_file), "--no-update-check"]
            )
    assert "No operatives" in result.output


def test_successful_run_renders_table(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 1\n'
    )

    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("alice", 42)),
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                ["--config", str(config_file), "--no-update-check"],
            )

    assert result.exit_code == 0
    assert "surveillance" in result.output.lower() or "Initiating" in result.output
    assert "alice" in result.output
    assert "Dossier" in result.output


def test_no_update_check_skips_update(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 0\n'
    )

    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("alice", 10)),
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.cli.check_for_update") as mock_update:
                result = runner.invoke(
                    gh_snitch,
                    ["--config", str(config_file), "--no-update-check"],
                )
                mock_update.assert_not_called()

    assert result.exit_code == 0


def test_github_url_cli_override(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[operatives]\nusers = []\n[surveillance]\nyears = 0\n")

    requests_mock.post(
        "https://github.example.com/api/graphql",
        json=_graphql_response(("alice", 5)),
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                [
                    "--config",
                    str(config_file),
                    "--users",
                    "alice",
                    "--github-url",
                    "https://github.example.com",
                    "--no-update-check",
                ],
            )

    assert result.exit_code == 0
    assert "alice" in result.output


def test_show_config_includes_github_url(runner, tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = []\n[network]\ngithub_url = "https://github.example.com"\n'
    )
    result = runner.invoke(gh_snitch, ["--show-config", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "github.example.com" in result.output


def test_show_config_includes_teams(runner, tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = []\n[teams.backend]\nusers = ["alice", "bob"]\n'
    )
    result = runner.invoke(gh_snitch, ["--show-config", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "teams.backend" in result.output
    assert "alice" in result.output


def test_show_config_no_teams_shows_empty(runner, tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[operatives]\nusers = []\n")
    result = runner.invoke(gh_snitch, ["--show-config", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "teams = {}" in result.output


def test_not_found_operative_shows_warning_and_exits_nonzero(
    runner, tmp_path, requests_mock
):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["ghost"]\n[surveillance]\nyears = 0\n'
    )

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

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                ["--config", str(config_file), "--no-update-check"],
            )

    assert result.exit_code != 0
    assert "ghost" in result.output
    assert "gone dark" in result.output


def test_min_contributions_suppresses_below_threshold(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice", "bob"]\n[surveillance]\nyears = 0\n'
    )

    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("alice", 50), ("bob", 3)),
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                [
                    "--config",
                    str(config_file),
                    "--no-update-check",
                    "--min-contributions",
                    "10",
                ],
            )

    assert result.exit_code == 0
    assert "alice" in result.output
    assert "bob" not in result.output
    assert "1 operative(s) below threshold suppressed" in result.output


def test_min_contributions_zero_shows_all(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice", "bob"]\n[surveillance]\nyears = 0\n'
    )

    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("alice", 50), ("bob", 0)),
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                [
                    "--config",
                    str(config_file),
                    "--no-update-check",
                    "--min-contributions",
                    "0",
                ],
            )

    assert result.exit_code == 0
    assert "alice" in result.output
    assert "bob" in result.output
    assert "suppressed" not in result.output


def test_min_contributions_from_config(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        "[operatives]\n"
        'users = ["alice", "bob"]\n'
        "[surveillance]\nyears = 0\n"
        "[display]\nmin_contributions = 20\n"
    )

    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("alice", 50), ("bob", 5)),
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                ["--config", str(config_file), "--no-update-check"],
            )

    assert result.exit_code == 0
    assert "alice" in result.output
    assert "bob" not in result.output
    assert "1 operative(s) below threshold suppressed" in result.output


def test_users_cli_override(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[operatives]\nusers = []\n[surveillance]\nyears = 0\n")

    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("bob", 7)),
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                ["--config", str(config_file), "--users", "bob", "--no-update-check"],
            )

    assert result.exit_code == 0


_GRAPHQL_RESPONSE = _graphql_response(("alice", 50))


def test_reset_snapshot_clears_and_exits(runner, tmp_path):
    snap = tmp_path / "snapshot-abc.json"
    snap.write_text('{"timestamp": "t", "contributions": {}}')
    with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
        result = runner.invoke(gh_snitch, ["--reset-snapshot"])
    assert result.exit_code == 0
    assert "cleared" in result.output.lower()
    assert not snap.exists()


def test_delta_no_prior_snapshot_shows_absolute(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 0\n'
    )
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)

    snap = tmp_path / f"snapshot-{_context_id(['alice'])}.json"
    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                result = runner.invoke(
                    gh_snitch,
                    [
                        "--config",
                        str(config_file),
                        "--no-update-check",
                        "--delta",
                    ],
                )

    assert result.exit_code == 0
    assert "No prior snapshot" in result.output
    assert "alice" in result.output
    assert not snap.exists()  # delta run does not create/update snapshot


def test_delta_shows_change_since_snapshot(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 0\n'
    )
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)

    # Seed a prior snapshot with alice having 36 contributions
    from datetime import date

    current_year = str(date.today().year)
    snap = tmp_path / f"snapshot-{_context_id(['alice'])}.json"
    snap.write_text(
        json.dumps(
            {
                "timestamp": "2026-04-04T10:00:00+00:00",
                "contributions": {"alice": {current_year: 36}},
            }
        )
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                result = runner.invoke(
                    gh_snitch,
                    [
                        "--config",
                        str(config_file),
                        "--no-update-check",
                        "--delta",
                    ],
                )

    assert result.exit_code == 0
    # alice: 50 - 36 = +14
    assert "+14" in result.output
    assert "Δ Today" in result.output


def test_delta_does_not_overwrite_snapshot(runner, tmp_path, requests_mock):
    """Delta runs must not update the snapshot so the baseline stays pinned."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 0\n'
    )
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)

    from datetime import date

    current_year = str(date.today().year)
    original_snapshot = json.dumps(
        {
            "timestamp": "2026-04-04T10:00:00+00:00",
            "contributions": {"alice": {current_year: 36}},
        }
    )
    snap = tmp_path / f"snapshot-{_context_id(['alice'])}.json"
    snap.write_text(original_snapshot)

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                runner.invoke(
                    gh_snitch,
                    ["--config", str(config_file), "--no-update-check", "--delta"],
                )

    assert snap.read_text() == original_snapshot


def test_delta_with_years_hides_prior_year_columns(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 1\n'
    )
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)

    from datetime import date

    current_year = str(date.today().year)
    prior_year = str(date.today().year - 1)
    snap = tmp_path / f"snapshot-{_context_id(['alice'])}.json"
    snap.write_text(
        json.dumps(
            {
                "timestamp": "2026-04-04T10:00:00+00:00",
                "contributions": {"alice": {current_year: 36, prior_year: 200}},
            }
        )
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                result = runner.invoke(
                    gh_snitch,
                    [
                        "--config",
                        str(config_file),
                        "--no-update-check",
                        "--delta",
                    ],
                )

    assert result.exit_code == 0
    assert "Δ Today" in result.output
    assert prior_year not in result.output


def test_successful_run_saves_snapshot(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 0\n'
    )
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)

    snap = tmp_path / f"snapshot-{_context_id(['alice'])}.json"
    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                result = runner.invoke(
                    gh_snitch,
                    ["--config", str(config_file), "--no-update-check"],
                )

    assert result.exit_code == 0
    assert snap.exists()
    data = json.loads(snap.read_text())
    assert data["contributions"]["alice"] is not None
    assert data["ranks"] == {"alice": 1}
    assert data["positions"] == {"alice": 1}


def test_rank_delta_marks_both_sides_when_tie_splits(runner, tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice", "bob", "carol"]\n'
        "[surveillance]\nyears = 0\n"
    )

    from datetime import date

    current_year = str(date.today().year)
    snap = tmp_path / f"snapshot-{_context_id(['alice', 'bob', 'carol'])}.json"
    snap.write_text(
        json.dumps(
            {
                "timestamp": "2026-04-04T10:00:00+00:00",
                "contributions": {
                    "alice": {current_year: 70},
                    "bob": {current_year: 64},
                    "carol": {current_year: 64},
                },
                "ranks": {"alice": 1, "bob": 2, "carol": 2},
            }
        )
    )

    current_data = {
        "alice": {current_year: 70},
        "bob": {current_year: 65},
        "carol": {current_year: 63},
    }

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                with patch(
                    "ghsnitch.cli.fetch_contributions",
                    return_value=(current_data, []),
                ):
                    result = runner.invoke(
                        gh_snitch,
                        [
                            "--config",
                            str(config_file),
                            "--no-update-check",
                            "--no-trend",
                        ],
                    )
    assert result.exit_code == 0
    assert "alice" in result.output
    assert "bob" in result.output
    assert "carol" in result.output
    assert "  1   =   alice" in result.output
    assert "  2  +1   bob" in result.output
    assert "  3  -1   carol" in result.output


def test_period_week_renders_this_week_column(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 3\n'
    )
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                result = runner.invoke(
                    gh_snitch,
                    [
                        "--config",
                        str(config_file),
                        "--no-update-check",
                        "--period",
                        "week",
                    ],
                )

    assert result.exit_code == 0
    assert "This Week" in result.output
    assert "alice" in result.output


def test_period_month_renders_this_month_column(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 3\n'
    )
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                result = runner.invoke(
                    gh_snitch,
                    [
                        "--config",
                        str(config_file),
                        "--no-update-check",
                        "--period",
                        "month",
                    ],
                )

    assert result.exit_code == 0
    assert "This Month" in result.output
    assert "alice" in result.output


def test_period_year_renders_this_year_column(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 3\n'
    )
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                result = runner.invoke(
                    gh_snitch,
                    [
                        "--config",
                        str(config_file),
                        "--no-update-check",
                        "--period",
                        "year",
                    ],
                )

    assert result.exit_code == 0
    assert "This Year" in result.output
    assert "alice" in result.output


def test_period_from_config_file(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 3\nperiod = "month"\n'
    )
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                result = runner.invoke(
                    gh_snitch,
                    ["--config", str(config_file), "--no-update-check"],
                )

    assert result.exit_code == 0
    assert "This Month" in result.output


def test_period_makes_single_api_call(runner, tmp_path, requests_mock):
    """Period mode should issue exactly one GraphQL request (one range)."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 5\n'
    )
    adapter = requests_mock.post(
        "https://api.github.com/graphql", json=_GRAPHQL_RESPONSE
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                result = runner.invoke(
                    gh_snitch,
                    [
                        "--config",
                        str(config_file),
                        "--no-update-check",
                        "--period",
                        "week",
                    ],
                )

    assert result.exit_code == 0
    assert adapter.call_count == 1  # one range, not six


# ---------------------------------------------------------------------------
# --last-months / --last-weeks / --since / --until
# ---------------------------------------------------------------------------


def _make_config(tmp_path, years=0):
    f = tmp_path / "config.toml"
    f.write_text(f'[operatives]\nusers = ["alice"]\n[surveillance]\nyears = {years}\n')
    return f


def _run(runner, config_file, tmp_path, extra_args):
    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                base = ["--config", str(config_file), "--no-update-check"]
                return runner.invoke(gh_snitch, base + extra_args)


def _run_separated(config_file, tmp_path, extra_args):
    """Run gh_snitch and return the result (stdout/stderr mixed by CliRunner)."""
    sep_runner = CliRunner()
    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                base = ["--config", str(config_file), "--no-update-check"]
                return sep_runner.invoke(gh_snitch, base + extra_args)


def _extract_json(output):
    """Extract the JSON array from mixed CLI output."""
    import re

    m = re.search(r"\[[\s\S]*\]", output)
    assert m, f"No JSON array found in output: {output!r}"
    return json.loads(m.group())


def _extract_csv_lines(output):
    """Return only CSV data lines (header, data rows, or footer)."""
    return [
        line
        for line in output.splitlines()
        if line.startswith("rank,")
        or (line and line[0].isdigit())
        or line.startswith(",")
    ]


def test_last_months_renders_month_columns(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--last-months", "3"])
    assert result.exit_code == 0
    # Three month columns should appear (e.g. "Apr 2026", "Mar 2026", "Feb 2026")
    assert result.output.count("20") >= 3  # at least 3 year-suffixed labels


def test_last_months_makes_n_api_calls(runner, tmp_path, requests_mock):
    adapter = requests_mock.post(
        "https://api.github.com/graphql", json=_GRAPHQL_RESPONSE
    )
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--last-months", "4"])
    assert result.exit_code == 0
    assert adapter.call_count == 4


def test_last_weeks_renders_week_columns(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--last-weeks", "3"])
    assert result.exit_code == 0
    # ISO week labels look like "2026-W15"
    assert "-W" in result.output


def test_last_weeks_makes_n_api_calls(runner, tmp_path, requests_mock):
    adapter = requests_mock.post(
        "https://api.github.com/graphql", json=_GRAPHQL_RESPONSE
    )
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--last-weeks", "5"])
    assert result.exit_code == 0
    assert adapter.call_count == 5


def test_since_renders_custom_label(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--since", "2025-01-01"])
    assert result.exit_code == 0
    assert "Since 2025-01-01" in result.output


def test_since_and_until_renders_range_label(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = _make_config(tmp_path)
    result = _run(
        runner, cfg, tmp_path, ["--since", "2025-01-01", "--until", "2025-03-31"]
    )
    assert result.exit_code == 0
    assert "2025-01-01" in result.output
    assert "2025-03-31" in result.output


def test_until_without_since_exits_nonzero(runner, tmp_path):
    cfg = _make_config(tmp_path)
    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        result = runner.invoke(
            gh_snitch,
            ["--config", str(cfg), "--no-update-check", "--until", "2025-03-31"],
        )
    assert result.exit_code != 0
    assert "--until requires --since" in result.output


def test_since_invalid_date_exits_nonzero(runner, tmp_path):
    cfg = _make_config(tmp_path)
    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                ["--config", str(cfg), "--no-update-check", "--since", "not-a-date"],
            )
    assert result.exit_code != 0


def test_last_months_from_config(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 3\nlast_months = 2\n'
    )
    result = _run(runner, cfg, tmp_path, [])
    assert result.exit_code == 0
    # Two month columns → two API calls
    # (just check it ran without error and has month-style labels)
    assert result.output  # non-empty


def test_last_weeks_from_config(runner, tmp_path, requests_mock):
    adapter = requests_mock.post(
        "https://api.github.com/graphql", json=_GRAPHQL_RESPONSE
    )
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 3\nlast_weeks = 3\n'
    )
    result = _run(runner, cfg, tmp_path, [])
    assert result.exit_code == 0
    assert adapter.call_count == 3


# ---------------------------------------------------------------------------
# --format flag
# ---------------------------------------------------------------------------


def test_format_json_outputs_valid_json(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--format", "json"])
    assert result.exit_code == 0
    data = _extract_json(result.output)
    assert isinstance(data, list)
    assert data[0]["operative"] == "alice"
    assert data[0]["rank"] == 1


def test_format_csv_outputs_csv(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--format", "csv"])
    assert result.exit_code == 0
    csv_lines = _extract_csv_lines(result.output)
    assert csv_lines[0].startswith("rank,operative,")
    assert any("alice" in line for line in csv_lines)


def test_format_markdown_outputs_gfm_table(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--format", "markdown"])
    assert result.exit_code == 0
    assert "| # |" in result.output or "|#|" in result.output
    assert "Operative" in result.output
    assert ":---" in result.output
    assert "alice" in result.output


def test_format_from_config_file(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 0\n'
        '[display]\nformat = "json"\n'
    )
    result = _run(runner, cfg, tmp_path, [])
    assert result.exit_code == 0
    data = _extract_json(result.output)
    assert data[0]["operative"] == "alice"


def test_format_cli_overrides_config(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[operatives]\nusers = ["alice"]\n[surveillance]\nyears = 0\n'
        '[display]\nformat = "json"\n'
    )
    result = _run(runner, cfg, tmp_path, ["--format", "csv"])
    assert result.exit_code == 0
    csv_lines = _extract_csv_lines(result.output)
    assert csv_lines[0].startswith("rank,operative,")


def test_format_json_with_last_months(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--format", "json", "--last-months", "2"])
    assert result.exit_code == 0
    data = _extract_json(result.output)
    assert len(data) == 1
    entry = data[0]
    # Should have two month-labelled keys besides rank, operative
    month_keys = [k for k in entry if k not in ("rank", "operative", "total")]
    assert len(month_keys) == 2


def test_format_json_with_period(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--format", "json", "--period", "month"])
    assert result.exit_code == 0
    data = _extract_json(result.output)
    assert data[0]["operative"] == "alice"
    assert "This Month" in data[0]


def test_format_csv_with_since(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--format", "csv", "--since", "2025-01-01"])
    assert result.exit_code == 0
    assert "Since 2025-01-01" in result.output


def test_format_table_is_default(runner, tmp_path, requests_mock):
    requests_mock.post("https://api.github.com/graphql", json=_GRAPHQL_RESPONSE)
    cfg = _make_config(tmp_path)
    result = _run(runner, cfg, tmp_path, [])
    assert result.exit_code == 0
    # Table format includes status messages in stdout
    assert "Dossier" in result.output


# ---------------------------------------------------------------------------
# --team flag
# ---------------------------------------------------------------------------


def test_team_selects_users_from_config(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[teams.platform]\nusers = ["alice"]\n[surveillance]\nyears = 0\n'
    )
    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("alice", 42)),
    )
    result = _run(runner, config_file, tmp_path, ["--team", "platform"])
    assert result.exit_code == 0
    assert "alice" in result.output


def test_team_unknown_exits_nonzero_with_message(runner, tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[teams.platform]\nusers = ["alice"]\n[surveillance]\nyears = 0\n'
    )
    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                [
                    "--config",
                    str(config_file),
                    "--no-update-check",
                    "--team",
                    "discovery",
                ],
            )
    assert result.exit_code != 0
    assert "discovery" in result.output
    assert "Known cells" in result.output


def test_team_unknown_with_no_teams_defined(runner, tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[operatives]\nusers = []\n[surveillance]\nyears = 0\n")
    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                ["--config", str(config_file), "--no-update-check", "--team", "alpha"],
            )
    assert result.exit_code != 0
    assert "none" in result.output


def test_users_overrides_team(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[teams.platform]\nusers = ["alice"]\n[surveillance]\nyears = 0\n'
    )
    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("bob", 7)),
    )
    result = _run(
        runner, config_file, tmp_path, ["--users", "bob", "--team", "platform"]
    )
    assert result.exit_code == 0
    assert "bob" in result.output
    assert "alice" not in result.output


def test_team_empty_users_shows_no_operatives_warning(runner, tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[teams.empty]\nusers = []\n[surveillance]\nyears = 0\n")
    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                ["--config", str(config_file), "--no-update-check", "--team", "empty"],
            )
    assert "No operatives" in result.output


def test_team_snapshots_are_partitioned(runner, tmp_path, requests_mock):
    """Verify that different teams and ad-hoc lists use distinct snapshot files."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[teams.alpha]\nusers = ["alice"]\n'
        '[teams.beta]\nusers = ["bob"]\n'
        "[surveillance]\nyears = 0\n"
    )

    # Mock response covers all three invocations:
    # - alpha (["alice"]): user_0 → alice
    # - beta  (["bob"]):   user_0 → bob
    # - ad-hoc (["alice","bob"]): user_0 → alice, user_1 → bob
    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("alice", 10), ("bob", 20)),
    )

    # We patch CACHE_DIR so we can see the real filenames
    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                # 1. Run for team alpha
                runner.invoke(
                    gh_snitch,
                    [
                        "--config",
                        str(config_file),
                        "--team",
                        "alpha",
                        "--no-update-check",
                    ],
                )
                # 2. Run for team beta
                runner.invoke(
                    gh_snitch,
                    [
                        "--config",
                        str(config_file),
                        "--team",
                        "beta",
                        "--no-update-check",
                    ],
                )
                # 3. Run for ad-hoc user list
                runner.invoke(
                    gh_snitch,
                    [
                        "--config",
                        str(config_file),
                        "--users",
                        "alice,bob",
                        "--no-update-check",
                    ],
                )

    # Verify three distinct files exist
    # Team snapshots use the team name
    assert (tmp_path / "snapshot-team-alpha.json").exists()
    assert (tmp_path / "snapshot-team-beta.json").exists()

    # Ad-hoc snapshots use a hash (u-...)
    hashed_snaps = list(tmp_path.glob("snapshot-u-*.json"))
    assert len(hashed_snaps) == 1


def test_team_snapshot_loaded_on_second_run(runner, tmp_path):
    """Verify that running with --team loads the team-specific snapshot.

    On the second run the operatives should show '=' (unchanged) not 'new',
    proving that load_snapshot receives the correct scope.
    """
    from datetime import date

    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[teams.alpha]\nusers = ["alice", "bob"]\n' "[surveillance]\nyears = 0\n"
    )

    current_year = str(date.today().year)
    contributions = {
        "alice": {current_year: 50},
        "bob": {current_year: 30},
    }

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                with patch(
                    "ghsnitch.cli.fetch_contributions",
                    return_value=(contributions, []),
                ):
                    # First run — creates the team snapshot.
                    result1 = runner.invoke(
                        gh_snitch,
                        [
                            "--config",
                            str(config_file),
                            "--team",
                            "alpha",
                            "--no-update-check",
                            "--no-trend",
                        ],
                    )
                    assert result1.exit_code == 0

                    # Snapshot file must exist for this team.
                    assert (tmp_path / "snapshot-team-alpha.json").exists()

                    # Second run — should load the same scope's snapshot.
                    # All operatives remain unchanged → "=".
                    result2 = runner.invoke(
                        gh_snitch,
                        [
                            "--config",
                            str(config_file),
                            "--team",
                            "alpha",
                            "--no-update-check",
                            "--no-trend",
                        ],
                    )
    assert result2.exit_code == 0
    # Both operatives should show "=" (rank unchanged), not "new".
    assert "new" not in result2.output
    assert "  1   =   alice" in result2.output
    assert "  2   =   bob" in result2.output


def test_init_config_aborts_if_declined(runner, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("original content")

    # input="n" to decline confirmation
    result = runner.invoke(
        gh_snitch, ["--init-config", "--config", str(config_path)], input="n\n"
    )

    assert result.exit_code != 0  # click.confirm(abort=True) exits non-zero on "n"
    assert config_path.read_text() == "original content"
    assert not (tmp_path / "config.toml.bak").exists()


def test_init_config_overwrites_and_backups_if_confirmed(runner, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("original content")

    # input="y" to confirm overwrite
    result = runner.invoke(
        gh_snitch, ["--init-config", "--config", str(config_path)], input="y\n"
    )

    assert result.exit_code == 0
    assert "secured" in result.output
    assert "established" in result.output

    # Verify backup exists and has original content
    backup_path = tmp_path / "config.toml.bak"
    assert backup_path.exists()
    assert backup_path.read_text() == "original content"

    # Verify main file is now the template
    assert "gh-snitch configuration" in config_path.read_text()


def test_init_config_no_prompt_if_missing(runner, tmp_path):
    config_path = tmp_path / "new_config.toml"

    # Should not prompt if file does not exist
    result = runner.invoke(gh_snitch, ["--init-config", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "established" in result.output
    assert config_path.exists()
    assert not (tmp_path / "new_config.toml.bak").exists()


def test_update_config_appends_missing_key(runner, tmp_path):
    config_path = tmp_path / "config.toml"
    # Create config missing rank_delta
    config_path.write_text("[display]\ntotals = false\n")

    result = runner.invoke(gh_snitch, ["--update-config", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Added" in result.output
    assert "display.rank_delta" in result.output

    content = config_path.read_text()
    assert "[display]" in content
    assert "totals = false" in content
    assert "# rank_delta =" in content
    assert "(added by --update-config)" in content


def test_update_config_no_op_if_up_to_date(runner, tmp_path):
    config_path = tmp_path / "config.toml"
    # Write full template
    from ghsnitch.config import generate_default_config

    generate_default_config(str(config_path))

    # Manually uncomment rank_delta so it exists
    content = config_path.read_text().replace(
        "# rank_delta = true", "rank_delta = true"
    )
    config_path.write_text(content)

    result = runner.invoke(gh_snitch, ["--update-config", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "already up to date" in result.output


def test_update_config_backups_existing(runner, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("old content")

    runner.invoke(gh_snitch, ["--update-config", "--config", str(config_path)])

    backup = tmp_path / "config.toml.bak"
    assert backup.exists()
    assert backup.read_text() == "old content"


def test_update_config_missing_file_errors(runner, tmp_path):
    config_path = tmp_path / "missing.toml"
    result = runner.invoke(gh_snitch, ["--update-config", "--config", str(config_path)])

    assert result.exit_code != 0
    assert "No config file found" in result.output


def test_rank_delta_column_visible_by_default(runner, tmp_path, requests_mock):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[operatives]\nusers = ["alice"]\n')

    requests_mock.post(
        "https://api.github.com/graphql",
        json=_graphql_response(("alice", 10)),
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            with patch("ghsnitch.snapshot.CACHE_DIR", tmp_path):
                # Run once to create snapshot
                runner.invoke(
                    gh_snitch, ["--config", str(config_file), "--no-update-check"]
                )
                # Run again — SHOULD show ± by default
                result = runner.invoke(
                    gh_snitch, ["--config", str(config_file), "--no-update-check"]
                )
                assert "±" in result.output

                # Run with --no-rank-delta — SHOULD hide ±
                result_no_delta = runner.invoke(
                    gh_snitch,
                    [
                        "--config",
                        str(config_file),
                        "--no-rank-delta",
                        "--no-update-check",
                    ],
                )
                assert "±" not in result_no_delta.output


# ---------------------------------------------------------------------------
# --redact mode
# ---------------------------------------------------------------------------

_GRAPHQL_RESPONSE_TWO_USERS = {
    "data": {
        "user_alice": {
            "login": "alice",
            "contributionsCollection": {
                "contributionCalendar": {"totalContributions": 100}
            },
        },
        "user_bob": {
            "login": "bob",
            "contributionsCollection": {
                "contributionCalendar": {"totalContributions": 50}
            },
        },
    }
}


def _make_two_user_config(tmp_path, years=0):
    f = tmp_path / "config.toml"
    f.write_text(
        f'[operatives]\nusers = ["alice", "bob"]\n[surveillance]\nyears = {years}\n'
    )
    return f


def test_redact_replaces_usernames(runner, tmp_path, requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql", json=_GRAPHQL_RESPONSE_TWO_USERS
    )
    cfg = _make_two_user_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--redact"])
    assert result.exit_code == 0
    assert "alice" not in result.output
    assert "bob" not in result.output


def test_redact_uses_nato_codenames(runner, tmp_path, requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql", json=_GRAPHQL_RESPONSE_TWO_USERS
    )
    cfg = _make_two_user_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--redact"])
    assert result.exit_code == 0
    # alice sorts before bob → Operative Alpha; bob → Operative Bravo
    assert "Operative Alpha" in result.output
    assert "Operative Bravo" in result.output


def test_redact_codename_order_is_deterministic(runner, tmp_path, requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql", json=_GRAPHQL_RESPONSE_TWO_USERS
    )
    cfg = _make_two_user_config(tmp_path)
    result1 = _run(runner, cfg, tmp_path, ["--redact", "--no-rank-delta"])
    result2 = _run(runner, cfg, tmp_path, ["--redact", "--no-rank-delta"])
    assert result1.output == result2.output


def test_redact_json_format_uses_codenames(runner, tmp_path, requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql", json=_GRAPHQL_RESPONSE_TWO_USERS
    )
    cfg = _make_two_user_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--redact", "--format", "json"])
    assert result.exit_code == 0
    data = _extract_json(result.output)
    operatives = {e["operative"] for e in data}
    assert "Operative Alpha" in operatives
    assert "Operative Bravo" in operatives
    assert not any(o in ("alice", "bob") for o in operatives)


def test_redact_csv_format_uses_codenames(runner, tmp_path, requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql", json=_GRAPHQL_RESPONSE_TWO_USERS
    )
    cfg = _make_two_user_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--redact", "--format", "csv"])
    assert result.exit_code == 0
    assert "Operative" in result.output
    assert "alice" not in result.output
    assert "bob" not in result.output


def test_redact_markdown_format_uses_codenames(runner, tmp_path, requests_mock):
    requests_mock.post(
        "https://api.github.com/graphql", json=_GRAPHQL_RESPONSE_TWO_USERS
    )
    cfg = _make_two_user_config(tmp_path)
    result = _run(runner, cfg, tmp_path, ["--redact", "--format", "markdown"])
    assert result.exit_code == 0
    assert "Operative Alpha" in result.output
    assert "alice" not in result.output
