from pathlib import Path

from ghsnitch.xdg import get_cache_dir, get_config_dir, get_log_dir


def test_get_config_dir_absolute_override(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert get_config_dir() == tmp_path / "gh-snitch"


def test_get_config_dir_relative_ignored(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative/path")
    result = get_config_dir()
    assert result == Path.home() / ".config" / "gh-snitch"


def test_get_config_dir_empty_ignored(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    result = get_config_dir()
    assert result == Path.home() / ".config" / "gh-snitch"


def test_get_config_dir_unset_uses_default(monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert get_config_dir() == Path.home() / ".config" / "gh-snitch"


def test_get_cache_dir_absolute_override(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert get_cache_dir() == tmp_path / "gh-snitch"


def test_get_cache_dir_relative_ignored(monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", ".cache")
    result = get_cache_dir()
    assert result == Path.home() / ".cache" / "gh-snitch"


def test_get_cache_dir_empty_ignored(monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", "")
    result = get_cache_dir()
    assert result == Path.home() / ".cache" / "gh-snitch"


def test_get_cache_dir_unset_uses_default(monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    assert get_cache_dir() == Path.home() / ".cache" / "gh-snitch"


def test_get_log_dir_absolute_override(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert get_log_dir() == tmp_path / "gh-snitch"


def test_get_log_dir_relative_ignored(monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", "state")
    result = get_log_dir()
    assert result == Path.home() / ".local" / "state" / "gh-snitch"


def test_get_log_dir_empty_ignored(monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", "")
    result = get_log_dir()
    assert result == Path.home() / ".local" / "state" / "gh-snitch"


def test_get_log_dir_unset_uses_default(monkeypatch):
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    assert get_log_dir() == Path.home() / ".local" / "state" / "gh-snitch"
