import zipfile
from unittest.mock import patch
from xml.etree import ElementTree

import pytest
from xlsxwriter.exceptions import InvalidWorksheetName

from ghsnitch.excel import write_excel_report
from ghsnitch.report import ContributionReport

_SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _report(name, rows):
    """Return a minimal contribution report for workbook tests."""
    return ContributionReport(
        name=name,
        users=[row["username"] for row in rows],
        rows=rows,
        period_labels=["Q3 2026", "Q2 2026"],
        rank_deltas=None,
        ghost_usernames=set(),
        delta_column=None,
        suppressed_count=0,
        missing_delta_snapshot=False,
    )


def _workbook_sheet_names(path):
    """Return worksheet names from an OOXML workbook in document order."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    sheets = root.find(f"{{{_SPREADSHEET_NS}}}sheets")
    return [sheet.attrib["name"] for sheet in sheets]


def _worksheet_xml(path, index=1):
    """Return a parsed OOXML worksheet by one-based index."""
    with zipfile.ZipFile(path) as archive:
        return ElementTree.fromstring(archive.read(f"xl/worksheets/sheet{index}.xml"))


def test_write_excel_report_creates_ordered_safe_unique_team_sheets(tmp_path):
    reports = [
        _report(
            "Platform/West",
            [{"username": "alice", "Q3 2026": 20, "Q2 2026": 10}],
        ),
        _report(
            "platform:west",
            [{"username": "bob", "Q3 2026": 15, "Q2 2026": 5}],
        ),
    ]
    output = tmp_path / "teams.xlsx"

    write_excel_report(reports, output, "https://github.com", show_totals=True)

    assert output.exists()
    assert _workbook_sheet_names(output) == ["Platform_West", "platform_west (2)"]


def test_write_excel_report_rechecks_apostrophe_after_name_truncation(tmp_path):
    output = tmp_path / "apostrophe.xlsx"
    report = _report(
        f"{'A' * 30}'hidden suffix",
        [{"username": "alice", "Q3 2026": 20, "Q2 2026": 10}],
    )

    write_excel_report([report], output, "https://github.com")

    assert _workbook_sheet_names(output) == ["A" * 30]


def test_write_excel_report_uses_formulas_and_numeric_count_cells(tmp_path):
    output = tmp_path / "totals.xlsx"
    report = _report(
        None,
        [{"username": "alice", "Q3 2026": 20, "Q2 2026": 10}],
    )

    write_excel_report([report], output, "https://github.com", show_totals=True)

    worksheet = _worksheet_xml(output)
    formulas = [
        formula.text for formula in worksheet.findall(f".//{{{_SPREADSHEET_NS}}}f")
    ]
    count_cell = worksheet.find(f".//{{{_SPREADSHEET_NS}}}c[@r='C3']")
    row_total_cell = worksheet.find(f".//{{{_SPREADSHEET_NS}}}c[@r='E3']")
    footer_total_cell = worksheet.find(f".//{{{_SPREADSHEET_NS}}}c[@r='E4']")
    assert _workbook_sheet_names(output) == ["Dossier"]
    assert any(formula.startswith("SUM(") for formula in formulas)
    assert count_cell.attrib.get("t") is None
    assert count_cell.find(f"{{{_SPREADSHEET_NS}}}v").text == "20"
    assert row_total_cell.find(f"{{{_SPREADSHEET_NS}}}v").text == "30"
    assert footer_total_cell.find(f"{{{_SPREADSHEET_NS}}}v").text == "30"


def test_write_excel_report_hyperlinks_operatives_unless_redacted(tmp_path):
    report = _report(
        "Platform",
        [{"username": "alice", "Q3 2026": 20, "Q2 2026": 10}],
    )
    linked_output = tmp_path / "linked.xlsx"
    redacted_output = tmp_path / "redacted.xlsx"

    write_excel_report([report], linked_output, "https://github.com")
    write_excel_report(
        [report],
        redacted_output,
        "https://github.com",
        redact_map={"alice": "Operative Alpha"},
    )

    linked_sheet = _worksheet_xml(linked_output)
    redacted_sheet = _worksheet_xml(redacted_output)
    linked_formulas = [
        formula.text for formula in linked_sheet.findall(f".//{{{_SPREADSHEET_NS}}}f")
    ]
    redacted_formulas = [
        formula.text for formula in redacted_sheet.findall(f".//{{{_SPREADSHEET_NS}}}f")
    ]
    assert any(formula.startswith("HYPERLINK(") for formula in linked_formulas)
    assert not any(formula.startswith("HYPERLINK(") for formula in redacted_formulas)


def test_write_excel_report_writes_zero_state_sheet_for_empty_team(tmp_path):
    output = tmp_path / "empty.xlsx"

    write_excel_report(
        [_report("Dormant", [])], output, "https://github.com", show_totals=True
    )

    assert _workbook_sheet_names(output) == ["Dormant"]
    assert not _worksheet_xml(output).findall(f".//{{{_SPREADSHEET_NS}}}f")


def test_write_excel_report_refuses_to_overwrite_existing_file(tmp_path):
    output = tmp_path / "existing.xlsx"
    output.write_bytes(b"existing dossier")

    with pytest.raises(FileExistsError):
        write_excel_report([_report("Platform", [])], output, "https://github.com")

    assert output.read_bytes() == b"existing dossier"


def test_write_excel_report_uses_exclusive_copy_when_hard_links_are_unavailable(
    tmp_path,
):
    output = tmp_path / "fallback.xlsx"

    with patch("ghsnitch.excel.os.link", side_effect=OSError("unsupported")):
        write_excel_report([_report("Platform", [])], output, "https://github.com")

    assert output.exists()
    assert _workbook_sheet_names(output) == ["Platform"]


def test_write_excel_report_creates_parent_directories(tmp_path):
    output = tmp_path / "nested" / "reports" / "teams.xlsx"

    write_excel_report([_report("Platform", [])], output, "https://github.com")

    assert output.exists()


def test_write_excel_report_removes_temporary_file_after_failure(tmp_path):
    output = tmp_path / "failed.xlsx"

    with (
        patch(
            "ghsnitch.excel._write_report_worksheet",
            side_effect=InvalidWorksheetName("invalid sheet"),
        ),
        pytest.raises(InvalidWorksheetName),
    ):
        write_excel_report([_report("Platform", [])], output, "https://github.com")

    assert not output.exists()
    assert list(tmp_path.iterdir()) == []
