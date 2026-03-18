import pytest


@pytest.fixture
def isolate_cache(monkeypatch, tmp_path):
    """Monkeypatch XDG_CACHE_HOME to a temp directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_dir))
    return cache_dir
