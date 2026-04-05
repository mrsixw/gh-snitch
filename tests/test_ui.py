from unittest.mock import patch

from ghsnitch.ui import (
    _delta_cell,
    _grade_colour,
    _trend_indicator,
    make_hyperlink,
    render_table,
)


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


# --- show_totals tests ---


def test_render_table_totals_column_header():
    rows = [{"username": "alice", "2025": 100, "2024": 80}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025", "2024"], show_totals=True)
    assert "Total" in output


def test_render_table_totals_column_value():
    rows = [{"username": "alice", "2025": 100, "2024": 80}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025", "2024"], show_totals=True)
    # alice's total should be 180
    assert "180" in output


def test_render_table_totals_footer_row():
    rows = [
        {"username": "alice", "2025": 100, "2024": 80},
        {"username": "bob", "2025": 200, "2024": 120},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025", "2024"], show_totals=True)
    # per-year totals: 300, 200; grand total: 500
    assert "300" in output
    assert "200" in output
    assert "500" in output
    # "Total" label appears in the footer row
    lines = output.splitlines()
    assert any("Total" in line for line in lines)


def test_render_table_totals_single_operative():
    rows = [{"username": "alice", "2025": 50}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"], show_totals=True)
    # total column = 50, footer row total = 50
    assert output.count("50") >= 2


def test_render_table_totals_zero_contributions():
    rows = [{"username": "alice", "2025": 0}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"], show_totals=True)
    assert "Total" in output
    assert "0" in output


# --- show_percent tests ---


def test_render_table_percent_annotation_non_tty():
    rows = [
        {"username": "alice", "2025": 300},
        {"username": "bob", "2025": 100},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"], show_percent=True)
    # alice: 300/400 = 75%, bob: 100/400 = 25%
    assert "75%" in output
    assert "25%" in output


def test_render_table_percent_annotation_format():
    rows = [{"username": "alice", "2025": 200}, {"username": "bob", "2025": 200}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"], show_percent=True)
    # each operative: 50%
    assert "(50%)" in output


def test_render_table_percent_zero_total():
    # all-zero year: percentages should be 0% without division error
    rows = [{"username": "alice", "2025": 0}, {"username": "bob", "2025": 0}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"], show_percent=True)
    assert "(0%)" in output


def test_render_table_percent_and_totals_combined():
    rows = [
        {"username": "alice", "2025": 300},
        {"username": "bob", "2025": 100},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"], show_totals=True, show_percent=True)
    assert "75%" in output
    assert "25%" in output
    assert "Total" in output
    assert "400" in output  # grand total


def test_render_table_percent_without_totals():
    # --percent without --totals is valid: no Total header
    rows = [{"username": "alice", "2025": 100}, {"username": "bob", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"], show_totals=False, show_percent=True)
    assert "(50%)" in output
    assert "Total" not in output


# --- _delta_cell tests ---


def test_delta_cell_positive_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _delta_cell(14) == "+14"


def test_delta_cell_negative_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _delta_cell(-5) == "-5"


def test_delta_cell_zero_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _delta_cell(0) == "0"


def test_delta_cell_positive_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _delta_cell(10)
    assert "+10" in result
    assert "\033[32m" in result  # green


def test_delta_cell_negative_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _delta_cell(-3)
    assert "-3" in result
    assert "\033[31m" in result  # red


def test_delta_cell_zero_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _delta_cell(0)
    assert "0" in result
    assert "\033[2m" in result  # dim


# --- render_table delta_col tests ---


def test_render_table_delta_col_shows_plus_prefix():
    rows = [{"username": "alice", "Δ Today": 14, "2024": 412}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["Δ Today", "2024"], delta_col="Δ Today")
    assert "+14" in output
    assert "Δ Today" in output


def test_render_table_delta_col_shows_negative():
    rows = [{"username": "alice", "Δ Today": -5, "2024": 412}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["Δ Today", "2024"], delta_col="Δ Today")
    assert "-5" in output


def test_render_table_delta_col_no_trend():
    # delta_col suppresses trend (caller passes show_trend=False)
    rows = [{"username": "alice", "Δ Today": 10, "2024": 412}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(
            rows, ["Δ Today", "2024"], delta_col="Δ Today", show_trend=False
        )
    assert "Trend" not in output


def test_render_table_delta_col_non_delta_column_still_graded():
    # The non-delta year column should still render as a plain count
    rows = [
        {"username": "alice", "Δ Today": 10, "2024": 412},
        {"username": "bob", "Δ Today": 5, "2024": 200},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["Δ Today", "2024"], delta_col="Δ Today")
    assert "412" in output
    assert "200" in output
