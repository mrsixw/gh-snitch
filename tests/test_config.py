from ghsnitch.config import generate_default_config, load_config


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
