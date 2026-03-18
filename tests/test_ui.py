from unittest.mock import patch

from ghsnitch.ui import _grade_colour, make_hyperlink, render_table


def test_grade_colour_all_zeros():
    prefix, suffix = _grade_colour(0, [0, 0, 0])
    assert "2;37" in prefix  # dim grey


def test_grade_colour_zero_value():
    prefix, suffix = _grade_colour(0, [100, 200, 300])
    assert "2;37" in prefix  # dim grey regardless of column


def test_grade_colour_top_quartile():
    column_values = [10, 20, 30, 100]
    prefix, suffix = _grade_colour(100, column_values)
    assert "1;32" in prefix  # bright green


def test_grade_colour_bottom_quartile():
    column_values = [1, 10, 100, 1000]
    prefix, suffix = _grade_colour(1, column_values)
    assert "31" in prefix  # red


def test_grade_colour_returns_reset_suffix():
    _, suffix = _grade_colour(50, [10, 50, 100])
    assert suffix == "\033[0m"


def test_make_hyperlink_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = make_hyperlink("https://example.com", "click me")
    assert "\033]8;;" in result
    assert "click me" in result
    assert "https://example.com" in result


def test_make_hyperlink_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        result = make_hyperlink("https://example.com", "click me")
    assert result == "click me"


def test_render_table_headers():
    rows = [{"username": "alice", "2025": 100, "2024": 80}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025", "2024"])
    assert "Operative" in output
    assert "2025" in output
    assert "2024" in output


def test_render_table_sorted_by_current_year():
    rows = [
        {"username": "alice", "2025": 50, "2024": 200},
        {"username": "bob", "2025": 200, "2024": 50},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025", "2024"])
    # bob has more current year contributions, should appear first
    bob_pos = output.index("bob")
    alice_pos = output.index("alice")
    assert bob_pos < alice_pos


def test_render_table_empty_rows():
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table([], ["2025"])
    assert "no operatives" in output.lower()
