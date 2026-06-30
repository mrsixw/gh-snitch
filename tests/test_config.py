import tomllib

from ghsnitch.config import (
    generate_default_config,
    load_config,
    render_config,
    update_config,
)


def test_load_config_from_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["alice", "bob"]\n\n[surveillance]\nyears = 5\n'
    )
    cfg = load_config(str(config_file))
    assert cfg["users"] == ["alice", "bob"]
    assert cfg["years"] == 5


def test_load_config_github_url(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[network]\ngithub_url = "https://github.example.com"\n')
    cfg = load_config(str(config_file))
    assert cfg["github_url"] == "https://github.example.com"


def test_load_config_github_url_defaults_to_github_com(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[operatives]\nusers = []\n")
    cfg = load_config(str(config_file))
    assert cfg["github_url"] == "https://github.com"


def test_load_config_defaults_on_missing_file(tmp_path, capsys):
    cfg = load_config(str(tmp_path / "nonexistent.toml"))
    assert cfg["users"] == []
    assert cfg["years"] == 3
    captured = capsys.readouterr()
    assert "No handler config found" in captured.err


def test_load_config_defaults_for_missing_keys(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[operatives]\n")
    cfg = load_config(str(config_file))
    assert cfg["users"] == []
    assert cfg["years"] == 3
    assert cfg["period"] is None


def test_load_config_period(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[surveillance]\nyears = 2\nperiod = "month"\n')
    cfg = load_config(str(config_file))
    assert cfg["period"] == "month"
    assert cfg["years"] == 2


def test_load_config_period_defaults_to_none(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[surveillance]\nyears = 1\n")
    cfg = load_config(str(config_file))
    assert cfg["period"] is None


def test_load_config_last_months(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[surveillance]\nlast_months = 6\n")
    cfg = load_config(str(config_file))
    assert cfg["last_months"] == 6


def test_load_config_last_weeks(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[surveillance]\nlast_weeks = 8\n")
    cfg = load_config(str(config_file))
    assert cfg["last_weeks"] == 8


def test_load_config_last_months_defaults_to_none(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[surveillance]\nyears = 1\n")
    cfg = load_config(str(config_file))
    assert cfg["last_months"] is None
    assert cfg["last_weeks"] is None


def test_generate_default_config_creates_dirs(tmp_path):
    path = tmp_path / "nested" / "dir" / "config.toml"
    result = generate_default_config(str(path))
    assert result == path
    assert path.exists()
    content = path.read_text()
    assert "[operatives]" in content
    assert "[surveillance]" in content


def test_generate_default_config_default_path(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = generate_default_config()
    assert path.exists()
    assert "gh-snitch" in str(path)


def test_load_config_output_format(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[display]\nformat = "json"\n')
    cfg = load_config(str(config_file))
    assert cfg["output_format"] == "json"


def test_load_config_output_format_csv(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[display]\nformat = "csv"\n')
    cfg = load_config(str(config_file))
    assert cfg["output_format"] == "csv"


def test_load_config_output_format_defaults_to_table(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[operatives]\nusers = []\n")
    cfg = load_config(str(config_file))
    assert cfg["output_format"] == "table"


def test_generate_default_config_contains_format_comment(tmp_path):
    path = generate_default_config(str(tmp_path / "config.toml"))
    content = path.read_text()
    assert "format" in content


def test_generate_default_config_contains_teams_comment(tmp_path):
    path = generate_default_config(str(tmp_path / "config.toml"))
    content = path.read_text()
    assert "teams" in content


def test_load_config_teams_single(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[teams.platform]\nusers = ["alice", "bob"]\n')
    cfg = load_config(str(config_file))
    assert cfg["teams"] == {"platform": ["alice", "bob"]}


def test_load_config_teams_multiple(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[teams.platform]\nusers = ["alice"]\n\n[teams.backend]\nusers = ["bob"]\n'
    )
    cfg = load_config(str(config_file))
    assert cfg["teams"] == {"platform": ["alice"], "backend": ["bob"]}


def test_load_config_teams_defaults_to_empty_dict(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[operatives]\nusers = []\n")
    cfg = load_config(str(config_file))
    assert cfg["teams"] == {}


def test_load_config_teams_empty_on_missing_file(tmp_path, capsys):
    cfg = load_config(str(tmp_path / "nonexistent.toml"))
    assert cfg["teams"] == {}


def test_load_config_teams_alongside_operatives(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[operatives]\nusers = ["carol"]\n\n[teams.alpha]\nusers = ["alice", "bob"]\n'
    )
    cfg = load_config(str(config_file))
    assert cfg["users"] == ["carol"]
    assert cfg["teams"] == {"alpha": ["alice", "bob"]}


def test_update_config_does_not_add_display_users(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[display]\nmin_contributions = 10\n")
    added = update_config(str(config_file))
    assert "display.users" not in added
    assert "display.users" not in config_file.read_text()


def test_update_config_is_idempotent(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[display]\nmin_contributions = 10\n")
    update_config(str(config_file))
    added_second = update_config(str(config_file))
    assert added_second == []


def test_update_config_fresh_config_no_display_users(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[operatives]\nusers = ["alice"]\n')
    added = update_config(str(config_file))
    assert "display.users" not in added
    assert "display.users" not in config_file.read_text()


# --- render_config tests ---


def test_render_config_produces_valid_toml():
    cfg = {"users": ["alice", "bob"], "years": 3, "github_url": "https://github.com"}
    output = render_config(cfg)
    parsed = tomllib.loads(output)
    assert parsed["operatives"]["users"] == ["alice", "bob"]
    assert parsed["surveillance"]["years"] == 3


def test_render_config_users_in_output():
    cfg = {
        "users": ["alice", "bob", "carol"],
        "years": 3,
        "github_url": "https://github.com",
    }
    output = render_config(cfg)
    assert "alice" in output
    assert "bob" in output
    assert "carol" in output


def test_render_config_years_reflected():
    cfg = {"users": ["alice"], "years": 5, "github_url": "https://github.com"}
    output = render_config(cfg)
    assert "years = 5" in output


def test_render_config_default_github_url_is_commented():
    cfg = {"users": [], "years": 3, "github_url": "https://github.com"}
    output = render_config(cfg)
    assert 'github_url = "https://github.com"' not in output.replace("# ", "X")
    assert "github_url" in output


def test_render_config_custom_github_url_is_active():
    cfg = {"users": [], "years": 3, "github_url": "https://ghe.corp.com"}
    output = render_config(cfg)
    parsed = tomllib.loads(output)
    assert parsed["network"]["github_url"] == "https://ghe.corp.com"


def test_render_config_round_trips():
    cfg = {"users": ["alice", "bob"], "years": 2, "github_url": "https://github.com"}
    output = render_config(cfg)
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(output)
        tmp = f.name
    try:
        loaded = load_config(tmp)
        assert loaded["users"] == ["alice", "bob"]
        assert loaded["years"] == 2
    finally:
        os.unlink(tmp)
