"""Write contribution dossiers as styled Excel workbooks using XlsxWriter."""

import os
import re
import shutil
import tempfile
from pathlib import Path

import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

from .breakdown import (
    ContributionBreakdown,
    has_other_contributions,
    sum_breakdowns,
)

__all__ = [
    "write_excel_report",
]

_INVALID_WORKSHEET_CHARACTERS = re.compile(r"[\[\]:*?/\\]")
_MAX_WORKSHEET_NAME_LENGTH = 31


def _unique_worksheet_name(name, used_names):
    """Return an Excel-safe worksheet name unique within a workbook.

    Args:
        name: Requested worksheet name.
        used_names: Case-folded names already present in the workbook.

    Returns:
        str: Sanitised, truncated, and disambiguated worksheet name.
    """
    base_name = _INVALID_WORKSHEET_CHARACTERS.sub("_", name).strip().strip("'")
    base_name = base_name or "Dossier"
    candidate = base_name[:_MAX_WORKSHEET_NAME_LENGTH].strip("'") or "Dossier"
    suffix_number = 2

    while candidate.casefold() in used_names:
        suffix = f" ({suffix_number})"
        candidate = f"{base_name[: _MAX_WORKSHEET_NAME_LENGTH - len(suffix)]}{suffix}"
        suffix_number += 1

    used_names.add(candidate.casefold())
    return candidate


def _ranked_rows(rows, period_labels):
    """Return rows sorted with competition ranks for Excel output.

    Args:
        rows: Contribution rows keyed by username and period label.
        period_labels: Ordered labels whose first item determines rank.

    Returns:
        list[tuple[int, dict]]: Competition rank paired with each sorted row.
    """
    current_label = period_labels[0]
    sorted_rows = sorted(
        rows, key=lambda row: (-row.get(current_label, 0), row["username"])
    )
    ranked_rows = []
    previous_count = None
    previous_rank = None
    for index, row in enumerate(sorted_rows):
        count = row.get(current_label, 0)
        rank = previous_rank if count == previous_count else index + 1
        ranked_rows.append((rank, row))
        previous_count = count
        previous_rank = rank
    return ranked_rows


def _write_report_worksheet(  # noqa: PLR0913
    workbook,
    report,
    worksheet_name,
    github_url,
    *,
    show_totals=False,
    redact_map=None,
):
    """Populate one worksheet from an independent contribution report.

    Args:
        workbook: Active XlsxWriter workbook.
        report: Contribution report to write.
        worksheet_name: Valid unique worksheet name.
        github_url: GitHub base URL used for operative hyperlinks.
        show_totals: Whether to add formula-driven row and column totals.
        redact_map: Optional username-to-codename mapping.
    """
    has_breakdown = report.breakdowns is not None
    worksheet = workbook.add_worksheet(worksheet_name)
    worksheet.hide_gridlines(2)
    worksheet.freeze_panes(2, 3 if has_breakdown else 2)
    worksheet.set_landscape()
    worksheet.fit_to_pages(1, 0)
    worksheet.repeat_rows(0, 1)
    worksheet.set_tab_color("#2E7D32")
    if has_breakdown:
        worksheet.outline_settings(True, False, True, False)

    title_format = workbook.add_format(
        {
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#0B1F33",
            "font_size": 15,
            "align": "left",
            "valign": "vcenter",
        }
    )
    header_format = workbook.add_format(
        {
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#2E7D32",
            "align": "center",
            "valign": "vcenter",
            "bottom": 1,
            "bottom_color": "#1B5E20",
        }
    )
    rank_format = workbook.add_format({"align": "center", "num_format": "0"})
    count_format = workbook.add_format({"align": "right", "num_format": "#,##0"})
    operative_format = workbook.add_format({"align": "left"})
    link_format = workbook.add_format(
        {"font_color": "#0563C1", "underline": True, "align": "left"}
    )
    total_label_format = workbook.add_format(
        {"bold": True, "top": 1, "top_color": "#7F8C8D"}
    )
    total_count_format = workbook.add_format(
        {
            "bold": True,
            "align": "right",
            "num_format": "#,##0",
            "top": 1,
            "top_color": "#7F8C8D",
        }
    )
    empty_format = workbook.add_format(
        {"italic": True, "font_color": "#666666", "align": "left"}
    )
    category_total_format = workbook.add_format({"bold": True, "align": "left"})
    category_sub_format = workbook.add_format(
        {"align": "left", "font_color": "#555555", "indent": 1}
    )
    sub_count_format = workbook.add_format(
        {"align": "right", "num_format": "#,##0", "font_color": "#555555"}
    )

    period_start_col = 3 if has_breakdown else 2
    headers = (
        ["Rank", "Operative", "Category", *report.period_labels]
        if has_breakdown
        else ["Rank", "Operative", *report.period_labels]
    )
    if show_totals:
        headers.append("Total")
    last_column = len(headers) - 1
    title = f"Team Dossier: {report.name}" if report.name else "Operative Dossier"

    worksheet.set_row(0, 24)
    worksheet.merge_range(0, 0, 0, last_column, title, title_format)
    worksheet.set_row(1, 22)
    worksheet.write_row(1, 0, headers, header_format)

    ranked_rows = _ranked_rows(report.rows, report.period_labels)
    include_other = (
        has_other_contributions(
            report.breakdowns,
            users=[row["username"] for _, row in ranked_rows],
            period_labels=report.period_labels,
        )
        if has_breakdown
        else False
    )
    data_start_row = 2
    current_row = data_start_row
    for rank, row in ranked_rows:
        username = row["username"]
        display_name = redact_map.get(username, username) if redact_map else username
        worksheet.write_number(current_row, 0, rank, rank_format)
        if redact_map:
            worksheet.write(current_row, 1, display_name, operative_format)
        else:
            profile_url = f"{github_url.rstrip('/')}/{username}"
            escaped_url = profile_url.replace('"', '""')
            escaped_name = display_name.replace('"', '""')
            worksheet.write_formula(
                current_row,
                1,
                f'=HYPERLINK("{escaped_url}","{escaped_name}")',
                link_format,
                display_name,
            )

        if has_breakdown:
            worksheet.write(current_row, 2, "Total", category_total_format)

        for label_offset, label in enumerate(
            report.period_labels, start=period_start_col
        ):
            worksheet.write_number(
                current_row, label_offset, row.get(label, 0), count_format
            )

        if show_totals:
            first_period_cell = xl_rowcol_to_cell(current_row, period_start_col)
            last_period_cell = xl_rowcol_to_cell(
                current_row, period_start_col + len(report.period_labels) - 1
            )
            cached_total = sum(row.get(label, 0) for label in report.period_labels)
            worksheet.write_formula(
                current_row,
                last_column,
                f"=SUM({first_period_cell}:{last_period_cell})",
                count_format,
                cached_total,
            )

        current_row += 1

        if has_breakdown:
            period_items = {
                label: (
                    report.breakdowns.get(username, {}).get(label)
                    or ContributionBreakdown(total=row.get(label, 0))
                )
                for label in report.period_labels
            }
            summed = sum_breakdowns(period_items.values())
            for key, cat_label, total_val in summed.categories(
                include_other=include_other
            ):
                worksheet.set_row(current_row, None, None, {"level": 1})
                worksheet.write(current_row, 2, cat_label, category_sub_format)
                for label_offset, label in enumerate(
                    report.period_labels, start=period_start_col
                ):
                    item = period_items[label]
                    value = item.other if key == "other" else getattr(item, key)
                    worksheet.write_number(
                        current_row, label_offset, value, sub_count_format
                    )
                if show_totals:
                    first_period_cell = xl_rowcol_to_cell(current_row, period_start_col)
                    last_period_cell = xl_rowcol_to_cell(
                        current_row, period_start_col + len(report.period_labels) - 1
                    )
                    worksheet.write_formula(
                        current_row,
                        last_column,
                        f"=SUM({first_period_cell}:{last_period_cell})",
                        sub_count_format,
                        total_val,
                    )
                current_row += 1

    if not ranked_rows:
        worksheet.merge_range(
            data_start_row,
            0,
            data_start_row,
            last_column,
            "No operatives configured for this team.",
            empty_format,
        )
    else:
        data_end_row = current_row - 1
        worksheet.autofilter(1, 0, data_end_row, last_column)
        last_period_column = period_start_col + len(report.period_labels) - 1
        if not has_breakdown:
            worksheet.conditional_format(
                data_start_row,
                period_start_col,
                data_end_row,
                last_period_column,
                {
                    "type": "3_color_scale",
                    "min_color": "#F8696B",
                    "mid_color": "#FFEB84",
                    "max_color": "#63BE7B",
                },
            )

        if show_totals:
            total_row = data_end_row + 1
            worksheet.write(total_row, 1, "Total", total_label_format)
            if has_breakdown:
                worksheet.write(total_row, 2, "Total", total_label_format)
            for column in range(period_start_col, last_period_column + 1):
                first_data_cell = xl_rowcol_to_cell(data_start_row, column)
                last_data_cell = xl_rowcol_to_cell(data_end_row, column)
                cached_total = sum(
                    row.get(report.period_labels[column - period_start_col], 0)
                    for _, row in ranked_rows
                )
                if has_breakdown:
                    cat_start = xl_rowcol_to_cell(data_start_row, 2)
                    cat_end = xl_rowcol_to_cell(data_end_row, 2)
                    formula = (
                        f'=SUMIF({cat_start}:{cat_end},"Total",'
                        f"{first_data_cell}:{last_data_cell})"
                    )
                else:
                    formula = f"=SUM({first_data_cell}:{last_data_cell})"
                worksheet.write_formula(
                    total_row,
                    column,
                    formula,
                    total_count_format,
                    cached_total,
                )
            first_total_cell = xl_rowcol_to_cell(total_row, period_start_col)
            last_total_cell = xl_rowcol_to_cell(total_row, last_period_column)
            worksheet.write_formula(
                total_row,
                last_column,
                f"=SUM({first_total_cell}:{last_total_cell})",
                total_count_format,
                sum(
                    row.get(label, 0)
                    for _, row in ranked_rows
                    for label in report.period_labels
                ),
            )

    max_name_length = max(
        (
            (
                len(redact_map.get(row["username"], row["username"]))
                if redact_map
                else len(row["username"])
            )
            for _, row in ranked_rows
        ),
        default=len("Operative"),
    )
    worksheet.set_column(0, 0, 8, rank_format)
    worksheet.set_column(1, 1, min(max(max_name_length + 2, 16), 32))
    if has_breakdown:
        worksheet.set_column(2, 2, 14)
    for column, label in enumerate(report.period_labels, start=period_start_col):
        worksheet.set_column(column, column, min(max(len(label) + 2, 12), 18))
    if show_totals:
        worksheet.set_column(last_column, last_column, 12, count_format)


def _publish_completed_workbook(temporary_path, destination):
    """Publish a completed workbook without replacing an existing file.

    Args:
        temporary_path: Completed workbook in the destination directory.
        destination: User-requested output path.

    Raises:
        OSError: If the workbook cannot be published safely.
    """
    try:
        os.link(temporary_path, destination)
        return
    except FileExistsError:
        raise
    except OSError:
        # Some writable filesystems do not support hard links. An exclusive
        # copy retains the no-overwrite guarantee on those filesystems.
        destination_created = False
        try:
            with temporary_path.open("rb") as source:
                with destination.open("xb") as target:
                    destination_created = True
                    shutil.copyfileobj(source, target)
        except OSError:
            if destination_created:
                try:
                    destination.unlink(missing_ok=True)
                except OSError:
                    pass
            raise


def write_excel_report(
    reports,
    output_path,
    github_url,
    *,
    show_totals=False,
    redact_map=None,
):
    """Write ordered reports to a new Excel workbook.

    Args:
        reports: Ordered contribution reports. Each becomes one worksheet.
        output_path: Destination path for the new workbook.
        github_url: GitHub base URL used for operative hyperlinks.
        show_totals: Whether to add formula-driven totals.
        redact_map: Optional username-to-codename mapping.

    Returns:
        Path: Path to the created workbook.

    Raises:
        FileExistsError: If the destination already exists.
    """
    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError(f"Output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".gh-snitch-", suffix=".xlsx.tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)

    try:
        used_names = set()
        with xlsxwriter.Workbook(str(temporary_path)) as workbook:
            for report in reports:
                requested_name = report.name or "Dossier"
                worksheet_name = _unique_worksheet_name(requested_name, used_names)
                _write_report_worksheet(
                    workbook,
                    report,
                    worksheet_name,
                    github_url,
                    show_totals=show_totals,
                    redact_map=redact_map,
                )

        _publish_completed_workbook(temporary_path, destination)
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass

    return destination
