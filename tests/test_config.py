import tomllib

import pytest

import ghsnitch.config as config_module
from ghsnitch import config
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
    config_dir = tmp_path / "gh-snitch"
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)

    path = generate_default_config()

    assert path == config_dir / "config.toml"
    assert path.exists()


def test_generate_default_config_refuses_to_overwrite(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("operative config")

    with pytest.raises(FileExistsError):
        generate_default_config(str(config_file))

    assert config_file.read_text() == "operative config"


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
    assert 'github-url = "https://github.com"' not in output.replace("# ", "X")
    assert "github-url" in output


def test_render_config_custom_github_url_is_active():
    cfg = {"users": [], "years": 3, "github_url": "https://ghe.corp.com"}
    output = render_config(cfg)
    parsed = tomllib.loads(output)
    assert parsed["network"]["github-url"] == "https://ghe.corp.com"


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


# --- kebab-case migration (issue #146) --------------------------------------


_LEGACY_CONFIG = """\
[operatives]
users = ["alice"]

[surveillance]
years = 2
last_months = 6
last_weeks = 8

[network]
github_url = "https://ghe.example.com"

[display]
min_contributions = 5
rank_delta = false
"""

_KEBAB_CONFIG = (
    _LEGACY_CONFIG.replace("last_months", "last-months")
    .replace("last_weeks", "last-weeks")
    .replace("github_url", "github-url")
    .replace("min_contributions", "min-contributions")
    .replace("rank_delta", "rank-delta")
)


def _write(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


def test_kebab_case_keys_are_read(tmp_path):
    cfg = config.load_config(str(_write(tmp_path, _KEBAB_CONFIG)))
    assert cfg["last_months"] == 6
    assert cfg["last_weeks"] == 8
    assert cfg["github_url"] == "https://ghe.example.com"
    assert cfg["min_contributions"] == 5
    assert cfg["rank_delta"] is False


def test_legacy_snake_case_keys_still_work(tmp_path):
    # Nobody's existing config may break on upgrade.
    cfg = config.load_config(str(_write(tmp_path, _LEGACY_CONFIG)))
    assert cfg["last_months"] == 6
    assert cfg["last_weeks"] == 8
    assert cfg["github_url"] == "https://ghe.example.com"
    assert cfg["min_contributions"] == 5
    assert cfg["rank_delta"] is False


def test_legacy_keys_warn_and_name_their_replacement(tmp_path, capsys):
    config.load_config(str(_write(tmp_path, _LEGACY_CONFIG)))
    err = capsys.readouterr().err
    for old, new in (
        ("last_months", "last-months"),
        ("github_url", "github-url"),
        ("min_contributions", "min-contributions"),
        ("rank_delta", "rank-delta"),
    ):
        assert old in err and new in err


def test_kebab_case_keys_do_not_warn(tmp_path, capsys):
    config.load_config(str(_write(tmp_path, _KEBAB_CONFIG)))
    assert "deprecated" not in capsys.readouterr().err


def test_kebab_wins_when_both_spellings_are_present(tmp_path):
    # A half-migrated file must resolve predictably, not by TOML ordering.
    both = (
        "[operatives]\nusers = []\n\n[network]\n"
        'github_url = "https://old.example.com"\n'
        'github-url = "https://new.example.com"\n'
    )
    cfg = config.load_config(str(_write(tmp_path, both)))
    assert cfg["github_url"] == "https://new.example.com"


def test_update_config_migrates_legacy_spellings(tmp_path):
    path = _write(tmp_path, _LEGACY_CONFIG)
    changes = config.update_config(str(path))
    text = path.read_text()

    assert "github-url" in text
    assert "min-contributions" in text
    assert "rank-delta" in text
    # The old spellings are gone as keys, and the values survived.
    assert "\ngithub_url =" not in text
    assert 'github-url = "https://ghe.example.com"' in text
    assert any("github_url -> github-url" in c for c in changes)


def test_migrated_config_reloads_without_warnings(tmp_path, capsys):
    path = _write(tmp_path, _LEGACY_CONFIG)
    config.update_config(str(path))
    capsys.readouterr()
    cfg = config.load_config(str(path))
    assert "deprecated" not in capsys.readouterr().err
    assert cfg["github_url"] == "https://ghe.example.com"
    assert cfg["min_contributions"] == 5


def test_migration_leaves_prose_and_values_alone(tmp_path):
    # The rename anchors at line start, so a snake_case word inside a comment
    # or a string value must survive untouched.
    text = (
        '[operatives]\nusers = ["alice"]\n\n'
        "# github_url used to be spelled this way\n"
        "[network]\n"
        'github_url = "https://example.com/github_url/path"\n'
    )
    path = _write(tmp_path, text)
    config.update_config(str(path))
    result = path.read_text()
    assert "# github_url used to be spelled this way" in result
    assert "/github_url/path" in result
    assert 'github-url = "https://example.com/github_url/path"' in result


def test_render_config_emits_kebab_case(tmp_path):
    rendered = config.render_config({"users": ["a"], "github_url": "https://x.example"})
    assert "github-url" in rendered
    assert "\ngithub_url" not in rendered
    # And it must still round-trip through load_config.
    cfg = config.load_config(str(_write(tmp_path, rendered)))
    assert cfg["github_url"] == "https://x.example"
