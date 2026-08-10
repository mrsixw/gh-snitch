from unittest.mock import patch

from ghsnitch.report import build_contribution_report


def test_delta_tolerates_incomplete_contribution_mapping():
    """Treat a missing current-period value as zero during delta rendering."""
    previous_snapshot = {
        "contributions": {"missing": {"2026": 5}},
        "ranks": {"missing": 1},
    }

    with patch("ghsnitch.report.load_snapshot", return_value=previous_snapshot):
        report = build_contribution_report(
            None,
            ["missing"],
            {},
            ["2026"],
            "https://github.com",
            delta=True,
        )

    assert report.rows == [{"username": "missing", "Δ Today": -5}]
