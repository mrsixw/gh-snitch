from unittest.mock import patch

from ghsnitch.ui import _grade_colour, _trend_indicator, make_hyperlink, render_table


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
    assert "#" in output
    assert "Operative" in output
    assert "2025" in output
    assert "2024" in output


def test_render_table_rank_column():
    rows = [
        {"username": "alice", "2025": 200},
        {"username": "bob", "2025": 100},
        {"username": "carol", "2025": 50},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"])
    lines = [ln for ln in output.splitlines() if ln.strip() and not ln.startswith("-")]
    # First data row (alice) should have rank 1
    assert "1" in lines[1]
    assert "alice" in lines[1]
    # Second (bob) rank 2, third (carol) rank 3
    assert "2" in lines[2]
    assert "3" in lines[3]


def test_render_table_rank_ties():
    rows = [
        {"username": "alice", "2025": 100},
        {"username": "bob", "2025": 100},
        {"username": "carol", "2025": 50},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"])
    lines = [ln for ln in output.splitlines() if ln.strip() and not ln.startswith("-")]
    # alice and bob tie at rank 1; carol is rank 3 (competition ranking)
    assert "1" in lines[1]
    assert "1" in lines[2]
    assert "3" in lines[3]


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


# --- _trend_indicator tests ---


def test_trend_indicator_increase_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _trend_indicator(220, 200, 1.0) == "+"  # 10% increase


def test_trend_indicator_decrease_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _trend_indicator(180, 200, 1.0) == "-"  # 10% decrease


def test_trend_indicator_flat_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _trend_indicator(205, 200, 1.0) == "="  # 2.5% — within ±10%


def test_trend_indicator_exact_boundary_up_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _trend_indicator(110, 100, 1.0) == "+"  # exactly 10%


def test_trend_indicator_exact_boundary_down_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _trend_indicator(90, 100, 1.0) == "-"  # exactly -10%


def test_trend_indicator_zero_previous_with_activity_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _trend_indicator(50, 0, 1.0) == "+"  # new activity


def test_trend_indicator_both_zero_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _trend_indicator(0, 0, 1.0) == "="  # flat at zero


def test_trend_indicator_increase_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _trend_indicator(220, 200, 1.0)
    assert "↑" in result
    assert "\033[32m" in result  # green


def test_trend_indicator_decrease_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _trend_indicator(180, 200, 1.0)
    assert "↓" in result
    assert "\033[31m" in result  # red


def test_trend_indicator_flat_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _trend_indicator(205, 200, 1.0)
    assert "→" in result
    assert "\033[2m" in result  # dim


# --- _trend_indicator annualized tests ---


def test_trend_indicator_annualized_projects_up():
    # 100 contributions in first quarter → annualizes to ~400, vs 300 last year → ↑
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _trend_indicator(100, 300, 0.25) == "+"


def test_trend_indicator_annualized_projects_down():
    # 50 contributions at half year → annualizes to 100, vs 300 last year → ↓
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _trend_indicator(50, 300, 0.50) == "-"


def test_trend_indicator_annualized_projects_flat():
    # 150 contributions at half year → annualizes to 300, vs 300 last year → =
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _trend_indicator(150, 300, 0.50) == "="


# --- render_table trend column tests ---


def test_render_table_shows_trend_column_with_two_years():
    rows = [{"username": "alice", "2025": 220, "2024": 200}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025", "2024"], year_fraction=1.0)
    assert "Trend" in output


def test_render_table_no_trend_column_with_one_year():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"], year_fraction=1.0)
    assert "Trend" not in output


def test_render_table_no_trend_column_when_hidden():
    rows = [{"username": "alice", "2025": 220, "2024": 200}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(
            rows, ["2025", "2024"], year_fraction=1.0, show_trend=False
        )
    assert "Trend" not in output


def test_render_table_trend_values_non_tty():
    rows = [
        {"username": "alice", "2025": 220, "2024": 200},  # +10% → +
        {"username": "bob", "2025": 180, "2024": 200},  # -10% → -
        {"username": "charlie", "2025": 205, "2024": 200},  # +2.5% → =
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025", "2024"], year_fraction=1.0)
    assert "+" in output
    assert "-" in output
    assert "=" in output
