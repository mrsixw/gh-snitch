from ghsnitch.updater import _parse_version_tuple


def test_parse_version_tuple_normal():
    assert _parse_version_tuple("1.2.3") == (1, 2, 3)


def test_parse_version_tuple_single():
    assert _parse_version_tuple("42") == (42,)


def test_parse_version_tuple_empty_string():
    assert _parse_version_tuple("") == ()


def test_parse_version_tuple_invalid():
    assert _parse_version_tuple("not-a-version") == ()


def test_parse_version_tuple_prerelease_alpha():
    assert _parse_version_tuple("1.0.0a1") == (1, 0, 0)


def test_parse_version_tuple_prerelease_dash():
    assert _parse_version_tuple("1.0.0-beta") == (1, 0, 0)


def test_parse_version_tuple_prerelease_rc():
    assert _parse_version_tuple("2.1.0rc3") == (2, 1, 0)


def test_parse_version_tuple_prerelease_compares_correctly():
    # Pre-release 1.0.0a1 should parse as (1, 0, 0), not () —
    # so it compares equal to the release, not spuriously less than it.
    pre = _parse_version_tuple("1.0.0a1")
    release = _parse_version_tuple("1.0.0")
    assert pre == release


def test_parse_version_tuple_prerelease_does_not_trigger_false_update():
    # Installed pre-release must not compare as less than the same release.
    installed = _parse_version_tuple("0.25.0a1")
    latest = _parse_version_tuple("0.25.0")
    assert not (latest > installed)
