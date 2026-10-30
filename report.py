"""Writes the results to an Excel file people can actually open and read."""
import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def _tidy_sheet(ws):
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    ws.freeze_panes = "A2"
    for col in ws.columns:
        longest = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(longest + 3, 60)


def write_report(issues, summary, path):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        issues.to_excel(writer, sheet_name="All issues", index=False)

        # one sheet per problem type, handy when you only care about e.g. overdue invoices
        for issue_type, chunk in issues.groupby("issue_type"):
            chunk.to_excel(writer, sheet_name=issue_type[:31], index=False)

        for ws in writer.book.worksheets:
            _tidy_sheet(ws)
