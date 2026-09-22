"""The --watch refresh loop, driven with fake clock, sleep and screen."""

from datetime import datetime

import pytest

from ghsnitch.watch import run_watch


class _Harness:
    """Records what the loop did and ends it after a set number of sleeps."""

    def __init__(self, cycles):
        self.cycles = cycles
        self.clears = 0
        self.sleeps = []

    def clear(self):
        self.clears += 1

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        if len(self.sleeps) >= self.cycles:
            raise KeyboardInterrupt

    @staticmethod
    def now():
        return datetime(2026, 9, 22, 14, 5, 9)

    def run(self, refresh, interval=300, on_error=()):
        run_watch(
            refresh,
            interval,
            on_error=on_error,
            clear=self.clear,
            sleep=self.sleep,
            now=self.now,
        )


def test_refreshes_each_cycle_and_sleeps_the_interval():
    calls = []
    harness = _Harness(cycles=3)

    harness.run(lambda: calls.append("sweep"), interval=120)

    assert calls == ["sweep"] * 3
    assert harness.sleeps == [120, 120, 120]
    assert harness.clears == 3


def test_ctrl_c_signs_off_cleanly(capsys):
    _Harness(cycles=1).run(lambda: None)

    assert "Operative went dark. Signing off." in capsys.readouterr().err


def test_ctrl_c_during_a_refresh_also_signs_off(capsys):
    """Most of a cycle is spent waiting on GitHub, so that is where Ctrl-C lands."""

    def interrupted():
        raise KeyboardInterrupt

    _Harness(cycles=99).run(interrupted)

    assert "Signing off." in capsys.readouterr().err


def test_footer_stamps_the_refresh_time_and_next_interval(capsys):
    _Harness(cycles=1).run(lambda: None, interval=90)

    err = capsys.readouterr().err
    assert "Last refreshed 14:05:09" in err
    assert "next sweep in 90s" in err


class _Transient(Exception):
    pass


def test_a_listed_error_is_reported_and_the_watch_carries_on(capsys):
    outcomes = iter([_Transient("📡 Signal lost."), None])
    calls = []

    def flaky():
        calls.append("sweep")
        error = next(outcomes)
        if error:
            raise error

    _Harness(cycles=2).run(flaky, on_error=(_Transient,))

    assert calls == ["sweep", "sweep"]
    err = capsys.readouterr().err
    assert "📡 Signal lost." in err
    assert "retrying next cycle" in err


def test_an_unlisted_error_ends_the_watch():
    """Only errors the caller has vouched for as transient are retried."""

    def broken():
        raise RuntimeError("bug")

    with pytest.raises(RuntimeError):
        _Harness(cycles=5).run(broken, on_error=(_Transient,))
