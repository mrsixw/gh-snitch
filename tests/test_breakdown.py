"""Tests for contribution breakdown model, API, renderers, Excel, config, and CLI."""

import csv
import io
import json
import zipfile

import pytest
from click.testing import CliRunner

from ghsnitch import api, cli, config, ui
from ghsnitch.breakdown import (
    VALID_BREAKDOWN_STYLES,
    ContributionBreakdown,
    has_other_contributions,
    sum_breakdowns,
)
from ghsnitch.breakdown_ui import render_breakdown_table
from ghsnitch.excel import write_excel_report
from ghsnitch.report import ContributionReport, build_contribution_report


def _sample_data():
    rows = [
        {"username": "alice", "2026": 100, "2025": 80},
        {"username": "bob", "2026": 50, "2025": 40},
    ]
    breakdowns = {
        "alice": {
            "2026": ContributionBreakdown(
                total=100, commits=60, prs=15, reviews=12, issues=8, repos=2, private=3
            ),
            "2025": ContributionBreakdown(
                total=80, commits=50, prs=10, reviews=10, issues=5, repos=1, private=4
            ),
        },
        "bob": {
            "2026": ContributionBreakdown(
                total=50, commits=30, prs=8, reviews=6, issues=4, repos=0, private=2
            ),
            "2025": ContributionBreakdown(
                total=40, commits=25, prs=5, reviews=5, issues=3, repos=0, private=2
            ),
        },
    }
    return rows, ["2026", "2025"], breakdowns


# ── Model tests ──────────────────────────────────────────────────────────────


def test_breakdown_exact_match_and_other_reconciliation():
    exact = ContributionBreakdown(
        total=100, commits=60, prs=15, reviews=12, issues=8, repos=2, private=3
    )
    assert exact.category_sum == 100
    assert exact.other == 0
    assert "other" not in exact.to_dict(include_other=False)

    with_gap = ContributionBreakdown(
        total=105, commits=60, prs=15, reviews=12, issues=8
    )
    assert with_gap.category_sum == 95
    assert with_gap.other == 10
    assert with_gap.to_dict(include_other=True)["other"] == 10

    negative_gap = ContributionBreakdown(total=10, commits=12)
    assert negative_gap.other == -2
    assert has_other_contributions({"alice": {"2026": negative_gap}})


def test_sum_breakdowns():
    a = ContributionBreakdown(
        total=10, commits=5, prs=2, reviews=1, issues=1, repos=0, private=1
    )
    b = ContributionBreakdown(
        total=20, commits=10, prs=3, reviews=4, issues=2, repos=1, private=0
    )
    summed = sum_breakdowns([a, b])
    assert summed == ContributionBreakdown(
        total=30, commits=15, prs=5, reviews=5, issues=3, repos=1, private=1
    )


# ── API tests ────────────────────────────────────────────────────────────────


def test_build_contributions_query_with_breakdown():
    plain_q, _ = api.build_contributions_query(
        ["alice"], "2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"
    )
    assert "totalCommitContributions" not in plain_q

    bd_q, variables = api.build_contributions_query(
        ["alice"],
        "2026-01-01T00:00:00Z",
        "2026-12-31T23:59:59Z",
        include_breakdown=True,
    )
    assert variables["login0"] == "alice"
    for field in (
        "totalCommitContributions",
        "totalPullRequestContributions",
        "totalPullRequestReviewContributions",
        "totalIssueContributions",
        "totalRepositoryContributions",
        "restrictedContributionsCount",
    ):
        assert field in bd_q


def test_fetch_contributions_with_breakdown(monkeypatch):
    def fake_post(query, github_url, cancel_event=None, variables=None):
        assert "totalCommitContributions" in query
        return {
            "data": {
                "user_0": {
                    "login": "alice",
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 100},
                        "totalCommitContributions": 60,
                        "totalPullRequestContributions": 15,
                        "totalPullRequestReviewContributions": 12,
                        "totalIssueContributions": 8,
                        "totalRepositoryContributions": 2,
                        "restrictedContributionsCount": 3,
                    },
                },
                "user_1": None,
            }
        }

    monkeypatch.setattr(api, "make_github_graphql_request", fake_post)
    ranges = [("2026", "2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z")]
    totals, breakdowns, not_found = api.fetch_contributions_with_breakdown(
        ["alice", "ghostuser", "bad handle!"], years=0, year_ranges=ranges
    )

    assert totals["alice"]["2026"] == 100
    assert breakdowns["alice"]["2026"] == ContributionBreakdown(
        total=100, commits=60, prs=15, reviews=12, issues=8, repos=2, private=3
    )
    assert not_found == {"ghostuser", "bad handle!"}
    assert breakdowns["ghostuser"]["2026"] == ContributionBreakdown()
    assert breakdowns["bad handle!"]["2026"] == ContributionBreakdown()


# ── Terminal breakdown renderers ─────────────────────────────────────────────


@pytest.mark.parametrize("style", VALID_BREAKDOWN_STYLES)
def test_render_breakdown_table_all_styles_plain(monkeypatch, style):
    monkeypatch.setattr(ui, "IS_TTY", False)
    rows, labels, breakdowns = _sample_data()
    output = render_breakdown_table(
        rows,
        labels,
        breakdowns,
        style=style,
        show_totals=True,
        show_percent=True,
        rank_deltas={"alice": 1, "bob": -1},
    )
    assert "alice" in output
    assert "bob" in output
    assert "Commits" in output
    assert "Issues" in output
    assert "Repos" not in output
    assert "Private" not in output
    assert "Other" not in output
    assert "60%" in output  # alice 60/100 commits in 2026
    assert "67%" in output  # alice 100/150 cohort share in 2026


@pytest.mark.parametrize("style", VALID_BREAKDOWN_STYLES)
def test_render_breakdown_table_tty_and_extended(monkeypatch, style):
    monkeypatch.setattr(ui, "IS_TTY", True)
    rows, labels, breakdowns = _sample_data()
    breakdowns["alice"]["2026"] = ContributionBreakdown(
        total=100, commits=60, prs=15, reviews=12, issues=8, repos=0, private=0
    )  # other == 5
    output = render_breakdown_table(
        rows,
        labels,
        breakdowns,
        style=style,
        extended=True,
        redact_map={"alice": "Operative Alpha", "bob": "Operative Bravo"},
    )
    assert "Operative Alpha" in output
    assert "alice" not in output
    assert "Repos" in output
    assert "Private" in output
    assert "Other" in output


def test_render_breakdown_table_empty_and_invalid_style():
    assert (
        render_breakdown_table([], ["2026"], {}, style="subrows")
        == "(no operatives configured)"
    )
    with pytest.raises(ValueError, match="Unknown breakdown style"):
        render_breakdown_table(
            [{"username": "alice", "2026": 1}], ["2026"], {}, style="bogus"
        )


def test_render_columns_groups_subcolumns_under_each_period(monkeypatch):
    monkeypatch.setattr(ui, "IS_TTY", False)
    rows, labels, breakdowns = _sample_data()
    output = render_breakdown_table(
        rows,
        labels,
        breakdowns,
        style="columns",
        show_totals=True,
    )
    lines = output.splitlines()
    # Both period headers appear on the same top header row (single table, not stacked).
    period_header_lines = [line for line in lines if "2026" in line and "2025" in line]
    assert len(period_header_lines) == 1
    assert "Trend" in output
    # Each period column has its own Commits subcolumn header on the second header row.
    sub_header_lines = [line for line in lines if line.count("Commits") == 3]
    assert len(sub_header_lines) == 1  # 2026, 2025, and Total


# ── Structured formats (JSON, CSV, Markdown, Excel) ──────────────────────────


def test_render_json_csv_markdown_with_breakdown():
    rows, labels, breakdowns = _sample_data()

    # JSON (default core 4)
    payload = json.loads(
        ui.render_json(rows, labels, show_totals=True, breakdowns=breakdowns)
    )
    assert payload[0]["operative"] == "alice"
    assert payload[0]["2026"] == {
        "total": 100,
        "commits": 60,
        "prs": 15,
        "reviews": 12,
        "issues": 8,
    }
    assert payload[0]["total"]["commits"] == 110

    # JSON (extended: includes repos, private, other)
    ext_payload = json.loads(
        ui.render_json(
            rows, labels, show_totals=True, breakdowns=breakdowns, extended=True
        )
    )
    assert ext_payload[0]["2026"] == {
        "total": 100,
        "commits": 60,
        "prs": 15,
        "reviews": 12,
        "issues": 8,
        "repos": 2,
        "private": 3,
        "other": 0,
    }

    # CSV
    csv_text = ui.render_csv(rows, labels, show_totals=True, breakdowns=breakdowns)
    parsed = list(csv.DictReader(io.StringIO(csv_text)))
    assert parsed[0]["category"] == "total"
    assert parsed[0]["2026"] == "100"
    assert parsed[1]["category"] == "commits"
    assert parsed[1]["2026"] == "60"
    assert parsed[-1]["operative"] == "Total"
    assert parsed[-1]["2026"] == "150"

    # Markdown (core 4 by default, extended adds Repos/Private/Other)
    md = ui.render_markdown(rows, labels, show_totals=True, breakdowns=breakdowns)
    assert "### 2026" in md
    assert "### 2025" in md
    assert "| # | Operative | Commits | PRs | Reviews | Issues | Total |" in md
    assert "**Total**" in md

    md_ext = ui.render_markdown(
        rows, labels, show_totals=True, breakdowns=breakdowns, extended=True
    )
    ext_header = (
        "| # | Operative | Commits | PRs | Reviews | Issues "
        "| Repos | Private | Other | Total |"
    )
    assert ext_header in md_ext


def test_render_multi_formats_with_breakdown():
    rows, labels, breakdowns = _sample_data()
    report = ContributionReport(
        name="core",
        users=["alice", "bob"],
        rows=rows,
        period_labels=labels,
        rank_deltas=None,
        ghost_usernames=set(),
        delta_column=None,
        suppressed_count=0,
        missing_delta_snapshot=False,
        breakdowns=breakdowns,
    )
    multi_json = json.loads(ui.render_multi_json([report], show_totals=True))
    assert multi_json["teams"][0]["team"] == "core"
    assert multi_json["teams"][0]["operatives"][0]["2026"]["commits"] == 60

    multi_csv = ui.render_multi_csv([report], show_totals=True)
    parsed = list(csv.DictReader(io.StringIO(multi_csv)))
    assert parsed[0]["team"] == "core"
    assert parsed[0]["category"] == "total"

    multi_md = ui.render_multi_markdown([report], show_totals=True)
    assert "## Team: core" in multi_md
    assert "### 2026" in multi_md


def test_excel_with_breakdown(tmp_path):
    rows, labels, breakdowns = _sample_data()
    report = ContributionReport(
        name="platform",
        users=["alice", "bob"],
        rows=rows,
        period_labels=labels,
        rank_deltas=None,
        ghost_usernames=set(),
        delta_column=None,
        suppressed_count=0,
        missing_delta_snapshot=False,
        breakdowns=breakdowns,
    )
    out = tmp_path / "breakdown.xlsx"
    write_excel_report([report], out, "https://github.com", show_totals=True)
    assert out.exists()

    with zipfile.ZipFile(out) as archive:
        sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        shared_strings = archive.read("xl/sharedStrings.xml").decode("utf-8")
    assert "Category" in shared_strings
    assert "Commits" in shared_strings
    assert 'outlineLevel="1"' in sheet_xml
    assert "SUMIF(" in sheet_xml


# ── Report + Config + CLI integration ────────────────────────────────────────


def test_report_preserves_breakdowns_after_filtering(monkeypatch, tmp_path):
    monkeypatch.setattr("ghsnitch.report.load_snapshot", lambda **kwargs: None)
    monkeypatch.setattr("ghsnitch.report.save_snapshot", lambda *args, **kwargs: None)
    _, labels, breakdowns = _sample_data()
    contributions = {
        "alice": {"2026": 100, "2025": 80},
        "bob": {"2026": 50, "2025": 40},
    }
    report = build_contribution_report(
        None,
        ["alice", "bob"],
        contributions,
        labels,
        "https://github.com",
        min_contributions=60,
        breakdowns=breakdowns,
    )
    assert [r["username"] for r in report.rows] == ["alice"]
    assert list(report.breakdowns.keys()) == ["alice"]


def test_config_breakdown_roundtrip(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[operatives]\nusers = ["alice"]\n\n[display]\n'
        'breakdown = true\nbreakdown-style = "NESTED"\n'
    )
    loaded = config.load_config(cfg_file)
    assert loaded["breakdown"] is True
    assert loaded["breakdown_style"] == "nested"

    exported = config.render_config(loaded)
    assert "breakdown = true" in exported
    assert 'breakdown-style = "nested"' in exported


def test_render_graph_and_stack_with_breakdown(monkeypatch):
    monkeypatch.setattr(ui, "IS_TTY", False)
    rows, labels, breakdowns = _sample_data()

    graph = ui.render_graph(rows, labels, breakdowns=breakdowns)
    assert "CATEGORY BREAKDOWN TREND" in graph
    assert "Commits" in graph
    assert "Private" not in graph
    assert "alice" not in graph

    graph_ext = ui.render_graph(rows, labels, breakdowns=breakdowns, extended=True)
    assert "Private" in graph_ext
    assert "Repos" in graph_ext
    assert "Other" in graph_ext

    stack = ui.render_stack(rows, labels, breakdowns=breakdowns)
    assert "STACKED CATEGORY BREAKDOWN" in stack
    assert "Commits" in stack
    assert "Private" not in stack
    assert "2025" in stack and "2026" in stack

    stack_ext = ui.render_stack(rows, labels, breakdowns=breakdowns, extended=True)
    assert "Private" in stack_ext
    assert "Repos" in stack_ext
    assert "Other" in stack_ext


def test_cli_breakdown_validations_and_execution(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli, "SECRET_GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr(ui, "IS_TTY", False)

    # Disallowed combination: --breakdown + --delta
    res_delta = runner.invoke(
        cli.gh_snitch,
        ["--users", "alice", "--breakdown", "--delta", "--no-update-check"],
    )
    assert res_delta.exit_code != 0
    assert "--delta" in res_delta.output

    # Happy paths: --breakdown, --breakdown-style (implicit enable), and graph/stack
    _, _, breakdowns = _sample_data()
    monkeypatch.setattr(
        cli,
        "fetch_contributions_with_breakdown",
        lambda *args, **kwargs: (
            {"alice": {"2026": 100, "2025": 80}},
            {"alice": breakdowns["alice"]},
            set(),
        ),
    )
    monkeypatch.setattr(
        cli,
        "get_year_ranges",
        lambda n: [
            ("2026", "2026-01-01T00:00:00+00:00", "2026-11-25T23:59:59+00:00"),
            ("2025", "2025-01-01T00:00:00+00:00", "2025-12-31T23:59:59+00:00"),
        ],
    )
    monkeypatch.setattr("ghsnitch.report.load_snapshot", lambda **kwargs: None)
    monkeypatch.setattr("ghsnitch.report.save_snapshot", lambda *args, **kwargs: None)

    res = runner.invoke(
        cli.gh_snitch,
        ["--users", "alice", "--years", "1", "--breakdown", "--no-update-check"],
    )
    assert res.exit_code == 0, res.output
    assert "Commits" in res.output
    assert "60" in res.output

    res_style = runner.invoke(
        cli.gh_snitch,
        [
            "--users",
            "alice",
            "--years",
            "1",
            "--breakdown-style",
            "columns",
            "--no-update-check",
        ],
    )
    assert res_style.exit_code == 0, res_style.output
    assert "Commits" in res_style.output

    res_ext = runner.invoke(
        cli.gh_snitch,
        [
            "--users",
            "alice",
            "--years",
            "1",
            "--breakdown-extended",
            "--no-update-check",
        ],
    )
    assert res_ext.exit_code == 0, res_ext.output
    assert "Repos" in res_ext.output
    assert "Private" in res_ext.output
    assert "Other" in res_ext.output

    for chart_fmt in ("graph", "stack"):
        res_chart = runner.invoke(
            cli.gh_snitch,
            [
                "--users",
                "alice",
                "--years",
                "1",
                "--breakdown",
                "--format",
                chart_fmt,
                "--no-update-check",
            ],
        )
        assert res_chart.exit_code == 0, res_chart.output
        assert "Commits" in res_chart.output
