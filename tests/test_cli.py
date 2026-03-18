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
