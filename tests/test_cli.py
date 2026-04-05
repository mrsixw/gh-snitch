from unittest.mock import patch

import pytest
from click.testing import CliRunner

from ghsnitch.cli import gh_snitch


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
        json={
            "data": {
                "user_alice": {
                    "login": "alice",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 42}
                    },
                }
            }
        },
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
        json={
            "data": {
                "user_alice": {
                    "login": "alice",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 10}
                    },
                }
            }
        },
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
        json={
            "data": {
                "user_alice": {
                    "login": "alice",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 5}
                    },
                }
            }
        },
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


def test_not_found_operative_shows_warning_and_exits_nonzero(
    runner, tmp_path, requests_mock
):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["ghost"]\n[surveillance]\nyears = 0\n'
    )

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
        json={
            "data": {
                "user_alice": {
                    "login": "alice",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 50}
                    },
                },
                "user_bob": {
                    "login": "bob",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 3}
                    },
                },
            }
        },
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
        json={
            "data": {
                "user_alice": {
                    "login": "alice",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 50}
                    },
                },
                "user_bob": {
                    "login": "bob",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 0}
                    },
                },
            }
        },
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
        json={
            "data": {
                "user_alice": {
                    "login": "alice",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 50}
                    },
                },
                "user_bob": {
                    "login": "bob",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 5}
                    },
                },
            }
        },
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
        json={
            "data": {
                "user_bob": {
                    "login": "bob",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 7}
                    },
                }
            }
        },
    )

    with patch("ghsnitch.cli.SECRET_GITHUB_TOKEN", "fake-token"):
        with patch("ghsnitch.api.SECRET_GITHUB_TOKEN", "fake-token"):
            result = runner.invoke(
                gh_snitch,
                ["--config", str(config_file), "--users", "bob", "--no-update-check"],
            )

    assert result.exit_code == 0
    assert "bob" in result.output
