import json
import os
from unittest.mock import patch

from ghsnitch.ui import (
    _delta_cell,
    _grade_colour,
    _rank_delta_cell,
    _trend_indicator,
    make_hyperlink,
    make_operative_cell,
    render_csv,
    render_graph,
    render_json,
    render_markdown,
    render_stack,
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
        assert _delta_cell(14, [5, 10, 14, 20]) == "+14"


def test_delta_cell_negative_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _delta_cell(-5, [0, 5, 10]) == "-5"


def test_delta_cell_zero_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _delta_cell(0, [0, 5, 10]) == "0"


def test_delta_cell_zero_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _delta_cell(0, [0, 5, 10])
    assert "0" in result
    assert "\033[2;31m" in result  # dim red


def test_delta_cell_positive_tty_uses_colour():
    # Positive delta should get a colour prefix (exact colour depends on month)
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _delta_cell(10, [5, 10, 15, 20])
    assert "+10" in result
    assert "\033[0m" in result  # reset present


def test_delta_cell_top_quartile_brightest():
    # Top-quartile value should get the last (brightest) palette entry
    col = [1, 2, 3, 100]
    with patch("ghsnitch.ui.IS_TTY", True):
        with patch(
            "ghsnitch.ui._delta_palette",
            return_value=[
                "\033[38;5;22m",
                "\033[38;5;34m",
                "\033[38;5;40m",
                "\033[38;5;46m",
            ],
        ):
            result = _delta_cell(100, col)
    assert "\033[38;5;46m" in result  # brightest green


def test_delta_cell_bottom_quartile_darkest():
    col = [1, 2, 3, 100]
    with patch("ghsnitch.ui.IS_TTY", True):
        with patch(
            "ghsnitch.ui._delta_palette",
            return_value=[
                "\033[38;5;22m",
                "\033[38;5;34m",
                "\033[38;5;40m",
                "\033[38;5;46m",
            ],
        ):
            result = _delta_cell(1, col)
    assert "\033[38;5;22m" in result  # darkest green


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


# --- _rank_delta_cell tests ---


def test_rank_delta_cell_up_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _rank_delta_cell(2) == "+2"


def test_rank_delta_cell_down_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _rank_delta_cell(-3) == "-3"


def test_rank_delta_cell_flat_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _rank_delta_cell(0) == "="


def test_rank_delta_cell_new_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        assert _rank_delta_cell(None) == "new"


def test_rank_delta_cell_up_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _rank_delta_cell(1)
    assert "↑1" in result
    assert "\033[32m" in result  # green


def test_rank_delta_cell_down_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _rank_delta_cell(-2)
    assert "↓2" in result
    assert "\033[31m" in result  # red


def test_rank_delta_cell_flat_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _rank_delta_cell(0)
    assert "=" in result
    assert "\033[2m" in result  # dim


def test_rank_delta_cell_new_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = _rank_delta_cell(None)
    assert "new" in result
    assert "\033[2m" in result  # dim


# --- render_table rank_deltas tests ---


def test_render_table_rank_delta_column_shown():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(
            rows, ["2025"], show_rank_delta=True, rank_deltas={"alice": 0}
        )
    assert "±" in output


def test_render_table_no_rank_delta_column_by_default():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"])
    assert "±" not in output


def test_render_table_rank_delta_up_non_tty():
    rows = [
        {"username": "alice", "2025": 200},
        {"username": "bob", "2025": 100},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(
            rows, ["2025"], show_rank_delta=True, rank_deltas={"alice": 2, "bob": -1}
        )
    assert "+2" in output
    assert "-1" in output


def test_render_table_rank_delta_flat_non_tty():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(
            rows, ["2025"], show_rank_delta=True, rank_deltas={"alice": 0}
        )
    assert "=" in output


def test_render_table_rank_delta_new_operative_non_tty():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(
            rows, ["2025"], show_rank_delta=True, rank_deltas={"alice": None}
        )
    assert "new" in output


def test_render_table_rank_delta_with_totals():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(
            rows,
            ["2025"],
            show_totals=True,
            show_rank_delta=True,
            rank_deltas={"alice": 1},
        )
    assert "±" in output
    assert "Total" in output


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


# ---------------------------------------------------------------------------
# render_json
# ---------------------------------------------------------------------------


def test_render_json_empty():
    assert render_json([], ["2025"]) == "[]"


def test_render_json_basic():
    rows = [
        {"username": "alice", "2025": 100},
        {"username": "bob", "2025": 200},
    ]
    output = render_json(rows, ["2025"])
    data = json.loads(output)
    assert len(data) == 2
    # bob has more contributions so should be ranked 1
    assert data[0]["operative"] == "bob"
    assert data[0]["rank"] == 1
    assert data[0]["2025"] == 200
    assert data[1]["operative"] == "alice"
    assert data[1]["rank"] == 2
    assert "\033" not in output


def test_render_json_with_totals():
    rows = [
        {"username": "alice", "2025": 100, "2024": 50},
    ]
    output = render_json(rows, ["2025", "2024"], show_totals=True)
    data = json.loads(output)
    assert data[0]["total"] == 150


def test_render_json_without_totals_has_no_total_key():
    rows = [{"username": "alice", "2025": 100}]
    output = render_json(rows, ["2025"], show_totals=False)
    data = json.loads(output)
    assert "total" not in data[0]


def test_render_json_tie_gives_same_rank():
    rows = [
        {"username": "alice", "2025": 100},
        {"username": "bob", "2025": 100},
    ]
    output = render_json(rows, ["2025"])
    data = json.loads(output)
    assert data[0]["rank"] == 1
    assert data[1]["rank"] == 1


def test_render_json_no_ansi_codes():
    rows = [{"username": "alice", "2025": 50}]
    output = render_json(rows, ["2025"])
    assert "\033[" not in output


# ---------------------------------------------------------------------------
# render_csv
# ---------------------------------------------------------------------------


def test_render_csv_empty():
    assert render_csv([], ["2025"]) == ""


def test_render_csv_basic():
    rows = [
        {"username": "alice", "2025": 100},
        {"username": "bob", "2025": 200},
    ]
    output = render_csv(rows, ["2025"])
    lines = output.strip().splitlines()
    assert lines[0] == "rank,operative,2025"
    # bob ranked first
    assert lines[1].startswith("1,bob,")
    assert lines[2].startswith("2,alice,")


def test_render_csv_with_totals_column_and_footer():
    rows = [
        {"username": "alice", "2025": 100, "2024": 50},
        {"username": "bob", "2025": 200, "2024": 80},
    ]
    output = render_csv(rows, ["2025", "2024"], show_totals=True)
    lines = output.strip().splitlines()
    assert "total" in lines[0]
    # footer row
    last = lines[-1]
    assert last.startswith(",Total,")
    # totals: 2025=300, 2024=130, grand=430
    assert "300" in last
    assert "130" in last
    assert "430" in last


def test_render_csv_no_ansi_codes():
    rows = [{"username": "alice", "2025": 50}]
    output = render_csv(rows, ["2025"])
    assert "\033[" not in output


def test_render_csv_multiple_labels():
    rows = [{"username": "alice", "Apr 2026": 10, "Mar 2026": 20}]
    output = render_csv(rows, ["Apr 2026", "Mar 2026"])
    lines = output.strip().splitlines()
    assert "Apr 2026" in lines[0]
    assert "Mar 2026" in lines[0]


# ---------------------------------------------------------------------------
# render_markdown
# ---------------------------------------------------------------------------


def test_render_markdown_empty():
    assert "(no operatives" in render_markdown([], ["2025"])


def test_render_markdown_basic():
    rows = [
        {"username": "alice", "2025": 100},
        {"username": "bob", "2025": 200},
    ]
    output = render_markdown(rows, ["2025"])
    lines = output.splitlines()
    # Header, separator, two data rows
    assert len(lines) == 4
    assert lines[0].startswith("|")
    assert "Operative" in lines[0]
    assert "2025" in lines[0]
    # Separator uses :--- for Operative and ---: for numbers
    assert ":---" in lines[1]
    assert "---:" in lines[1]
    # bob (200) should be first data row
    assert "bob" in lines[2]
    assert "alice" in lines[3]


def test_render_markdown_with_totals():
    rows = [
        {"username": "alice", "2025": 100, "2024": 50},
    ]
    output = render_markdown(rows, ["2025", "2024"], show_totals=True)
    assert "Total" in output
    assert "**Total**" in output
    lines = output.splitlines()
    # header + separator + 1 data row + 1 footer
    assert len(lines) == 4


def test_render_markdown_no_ansi_codes():
    rows = [{"username": "alice", "2025": 50}]
    output = render_markdown(rows, ["2025"])
    assert "\033[" not in output


def test_render_markdown_pipe_structure():
    rows = [{"username": "alice", "This Week": 7}]
    output = render_markdown(rows, ["This Week"])
    for line in output.splitlines():
        assert line.startswith("|")
        assert line.endswith("|")


# --- render_graph ---


def test_render_graph_basic():
    rows = [
        {"username": "alice", "2026": 100, "2025": 80},
        {"username": "bob", "2026": 50, "2025": 60},
    ]
    with patch("os.get_terminal_size", return_value=os.terminal_size((80, 24))):
        output = render_graph(rows, ["2026", "2025"])
    assert isinstance(output, str)
    assert len(output) > 0
    assert "alice" in output
    assert "bob" in output
    assert "OPERATIVE SURVEILLANCE DOSSIER" in output


def test_render_graph_single_operative():
    rows = [{"username": "alice", "2026": 100}]
    with patch("os.get_terminal_size", return_value=os.terminal_size((80, 24))):
        output = render_graph(rows, ["2026"])
    assert "alice" in output


def test_render_graph_single_period():
    rows = [
        {"username": "alice", "This Week": 10},
        {"username": "bob", "This Week": 5},
    ]
    with patch("os.get_terminal_size", return_value=os.terminal_size((80, 24))):
        output = render_graph(rows, ["This Week"])
    assert "This Week" in output


def test_render_graph_empty_rows():
    output = render_graph([], ["2026"])
    assert "no operatives configured" in output


def test_render_graph_all_zeros():
    rows = [
        {"username": "alice", "2026": 0},
        {"username": "bob", "2026": 0},
    ]
    with patch("os.get_terminal_size", return_value=os.terminal_size((80, 24))):
        output = render_graph(rows, ["2026"])
    assert "alice" in output
    assert "bob" in output


def test_render_graph_no_color():
    rows = [{"username": "alice", "2026": 100}]
    # IS_TTY is used in render_graph to decide whether to call colorless()
    with patch("ghsnitch.ui.IS_TTY", False):
        with patch("os.get_terminal_size", return_value=os.terminal_size((80, 24))):
            output = render_graph(rows, ["2026"])
    # ANSI escape sequences start with \033[
    assert "\033[" not in output


# ---------------------------------------------------------------------------
# Ghost operative indicator
# ---------------------------------------------------------------------------


def test_make_operative_cell_no_ghost():
    with patch("ghsnitch.ui.IS_TTY", False):
        result = make_operative_cell("alice", is_ghost=False)
    assert result == "alice"
    assert "ghost" not in result


def test_make_operative_cell_ghost_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        result = make_operative_cell("alice", is_ghost=True)
    assert "alice" in result
    assert "[ghost]" in result


def test_make_operative_cell_ghost_tty():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = make_operative_cell("alice", is_ghost=True)
    assert "alice" in result
    assert "👻" in result


def test_render_table_ghost_indicator_non_tty():
    rows = [
        {"username": "alice", "2025": 0, "2024": 0},
        {"username": "bob", "2025": 100, "2024": 80},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025", "2024"], ghost_usernames={"alice"})
    alice_line = next(ln for ln in output.splitlines() if "alice" in ln)
    bob_line = next(ln for ln in output.splitlines() if "bob" in ln)
    assert "[ghost]" in alice_line
    assert "[ghost]" not in bob_line


def test_render_table_ghost_indicator_tty():
    rows = [
        {"username": "alice", "2025": 0},
        {"username": "bob", "2025": 50},
    ]
    with patch("ghsnitch.ui.IS_TTY", True):
        output = render_table(rows, ["2025"], ghost_usernames={"alice"})
    assert "👻" in output


def test_render_table_no_ghost_when_not_provided():
    rows = [{"username": "alice", "2025": 0}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"])
    assert "[ghost]" not in output
    assert "👻" not in output


def test_render_table_non_ghost_unaffected():
    rows = [
        {"username": "alice", "2025": 0},
        {"username": "bob", "2025": 100},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"], ghost_usernames={"alice"})
    # bob has contributions and must not get the ghost mark
    bob_line = next(ln for ln in output.splitlines() if "bob" in ln)
    assert "[ghost]" not in bob_line


# ---------------------------------------------------------------------------
# --redact mode
# ---------------------------------------------------------------------------


def test_make_operative_cell_redact_non_tty():
    with patch("ghsnitch.ui.IS_TTY", False):
        result = make_operative_cell("alice", display_name="Operative Alpha")
    assert result == "Operative Alpha"
    assert "alice" not in result
    assert "\033]8;;" not in result


def test_make_operative_cell_redact_tty_no_hyperlink():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = make_operative_cell("alice", display_name="Operative Alpha")
    assert "Operative Alpha" in result
    assert "\033]8;;" not in result


def test_make_operative_cell_redact_with_ghost():
    with patch("ghsnitch.ui.IS_TTY", False):
        result = make_operative_cell(
            "alice", is_ghost=True, display_name="Operative Alpha"
        )
    assert "Operative Alpha" in result
    assert "[ghost]" in result
    assert "alice" not in result


def test_render_table_redact_uses_codename():
    rows = [
        {"username": "alice", "2025": 100},
        {"username": "bob", "2025": 50},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(
            rows,
            ["2025"],
            redact_map={"alice": "Operative Alpha", "bob": "Operative Bravo"},
        )
    assert "Operative Alpha" in output
    assert "Operative Bravo" in output
    assert "alice" not in output
    assert "bob" not in output


def test_render_table_redact_no_hyperlinks_tty():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", True):
        output = render_table(rows, ["2025"], redact_map={"alice": "Operative Alpha"})
    assert "\033]8;;" not in output


def test_render_table_no_redact_when_map_none():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"], redact_map=None)
    assert "alice" in output


def test_render_json_redact_operative_field():
    import json as _json

    rows = [{"username": "alice", "2025": 100}]
    output = render_json(rows, ["2025"], redact_map={"alice": "Operative Alpha"})
    data = _json.loads(output)
    assert data[0]["operative"] == "Operative Alpha"
    assert "alice" not in output


def test_render_csv_redact_operative_column():
    rows = [{"username": "alice", "2025": 100}]
    output = render_csv(rows, ["2025"], redact_map={"alice": "Operative Alpha"})
    assert "Operative Alpha" in output
    assert "alice" not in output


def test_render_markdown_redact_operative_column():
    rows = [{"username": "alice", "2025": 100}]
    output = render_markdown(rows, ["2025"], redact_map={"alice": "Operative Alpha"})
    assert "Operative Alpha" in output
    assert "alice" not in output


def test_render_table_redact_unmapped_shows_username():
    rows = [
        {"username": "alice", "2025": 100},
        {"username": "unknown", "2025": 50},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(rows, ["2025"], redact_map={"alice": "Operative Alpha"})
    assert "Operative Alpha" in output
    assert "unknown" in output


def test_render_table_redact_shows_year_columns():
    """Year data must appear in all columns — not just the operative name."""
    rows = [
        {"username": "alice", "2024": 80, "2025": 100},
        {"username": "bob", "2024": 40, "2025": 50},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(
            rows,
            ["2025", "2024"],
            redact_map={"alice": "Operative Alpha", "bob": "Operative Bravo"},
        )
    assert "100" in output
    assert "80" in output
    assert "50" in output
    assert "40" in output
    assert "alice" not in output
    assert "bob" not in output


def test_render_table_redact_with_percent():
    """--percent annotations must appear in redact mode."""
    rows = [{"username": "alice", "2025": 100}, {"username": "bob", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(
            rows,
            ["2025"],
            show_percent=True,
            redact_map={"alice": "Operative Alpha", "bob": "Operative Bravo"},
        )
    assert "50%" in output


def test_render_table_redact_with_totals():
    """--totals footer and per-row Total column must appear in redact mode."""
    rows = [{"username": "alice", "2024": 80, "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_table(
            rows,
            ["2025", "2024"],
            show_totals=True,
            redact_map={"alice": "Operative Alpha"},
        )
    assert "180" in output  # per-row total
    assert "Total" in output


def test_render_graph_redact_uses_codenames_in_legend():
    """Graph legend must show codenames, not real usernames."""
    rows = [
        {"username": "alice", "2024": 80, "2025": 100},
        {"username": "bob", "2024": 40, "2025": 50},
    ]
    with patch("ghsnitch.ui.IS_TTY", False):
        with patch(
            "os.get_terminal_size",
            return_value=__import__("os").terminal_size((80, 24)),
        ):  # noqa: E501
            output = render_graph(
                rows,
                ["2025", "2024"],
                redact_map={"alice": "Operative Alpha", "bob": "Operative Bravo"},
            )
    assert "Operative Alpha" in output
    assert "Operative Bravo" in output
    assert "alice" not in output
    assert "bob" not in output


# ---------------------------------------------------------------------------
# render_stack
# ---------------------------------------------------------------------------


def test_render_stack_empty_rows():
    assert "no operatives" in render_stack([], ["2025"]).lower()


def test_render_stack_contains_year_labels():
    rows = [{"username": "alice", "2024": 100, "2025": 200}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_stack(rows, ["2025", "2024"])
    assert "2024" in output
    assert "2025" in output


def test_render_stack_contains_operative_in_legend():
    rows = [{"username": "alice", "2025": 100}, {"username": "bob", "2025": 50}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_stack(rows, ["2025"])
    assert "alice" in output
    assert "bob" in output


def test_render_stack_zero_year_column_is_empty():
    """A year with zero total contributions must produce no filled cells."""
    rows = [{"username": "alice", "2024": 0, "2025": 500}]
    # x_labels = reversed(["2025","2024"]) = ["2024","2025"] — 2024 is the left column.
    with patch("ghsnitch.ui.IS_TTY", False):
        with patch("os.get_terminal_size", return_value=os.terminal_size((80, 24))):
            output = render_stack(rows, ["2025", "2024"])
    y_axis_width = 7
    col_width = 10  # deterministic for 80-wide terminal with 2 years
    body_lines = [ln for ln in output.splitlines() if "┤" in ln or "│" in ln]
    for ln in body_lines:
        left_cell = ln[y_axis_width : y_axis_width + col_width]
        assert "█" not in left_cell, f"Expected no blocks for zero year: {ln!r}"


def test_render_stack_no_ansi_in_non_tty():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_stack(rows, ["2025"])
    assert "\033[" not in output


def test_render_stack_ansi_in_tty():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", True):
        with patch("os.get_terminal_size", return_value=os.terminal_size((80, 30))):
            output = render_stack(rows, ["2025"])
    assert "\033[" in output


def test_render_stack_redact_shows_codenames():
    rows = [{"username": "alice", "2025": 100}, {"username": "bob", "2025": 50}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_stack(
            rows,
            ["2025"],
            redact_map={"alice": "Operative Alpha", "bob": "Operative Bravo"},
        )
    assert "Operative Alpha" in output
    assert "Operative Bravo" in output
    assert "alice" not in output
    assert "bob" not in output


def test_render_stack_all_zeros_does_not_crash():
    rows = [{"username": "alice", "2025": 0}, {"username": "bob", "2025": 0}]
    with patch("ghsnitch.ui.IS_TTY", False):
        output = render_stack(rows, ["2025"])
    assert output  # does not raise, returns something


# ---------------------------------------------------------------------------
# GitHub Enterprise URL support (#90)
# ---------------------------------------------------------------------------


def test_make_operative_cell_ghe_url_in_hyperlink():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = make_operative_cell("alice", github_url="https://github.example.com")
    assert "https://github.example.com/alice" in result
    assert "https://github.com" not in result


def test_make_operative_cell_default_url_is_github_com():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = make_operative_cell("alice")
    assert "https://github.com/alice" in result


def test_make_operative_cell_ghe_url_trailing_slash_normalised():
    with patch("ghsnitch.ui.IS_TTY", True):
        result = make_operative_cell("alice", github_url="https://github.example.com/")
    assert "https://github.example.com/alice" in result
    assert "//alice" not in result


def test_render_table_ghe_url_in_cells():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", True):
        output = render_table(rows, ["2025"], github_url="https://github.example.com")
    assert "https://github.example.com/alice" in output
    assert "https://github.com" not in output


def test_render_table_default_url_is_github_com():
    rows = [{"username": "alice", "2025": 100}]
    with patch("ghsnitch.ui.IS_TTY", True):
        output = render_table(rows, ["2025"])
    assert "https://github.com/alice" in output
