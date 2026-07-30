"""
report_generator.py
--------------------
Solutions 3, 4, 5: individual client reports, combined reports
(all/branch/scheme-wise), and custom date-range reports -- generated
on demand instead of manual Excel filtering.
"""

import os
from datetime import datetime
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

REPORT_COLUMNS = [
    "investor_name", "ucc", "folio_no", "scheme", "sip_amount",
    "sip_start_date", "sip_end_date", "next_due_date", "status",
    "risk_level", "missed_count",
]
COLUMN_LABELS = {
    "investor_name": "Investor Name", "ucc": "UCC", "folio_no": "Folio No",
    "scheme": "Scheme", "sip_amount": "SIP Amount", "sip_start_date": "Start Date",
    "sip_end_date": "End Date", "next_due_date": "Next Due", "status": "Status",
    "risk_level": "Risk", "missed_count": "Missed",
}
# Proportional widths (points) for landscape A4 (~780pt usable width after
# margins) -- Investor Name and Scheme get the most room since they hold
# the longest text; everything wraps instead of overflowing the page.
COLUMN_WIDTHS = {
    "investor_name": 95, "ucc": 55, "folio_no": 70, "scheme": 155,
    "sip_amount": 55, "sip_start_date": 60, "sip_end_date": 60,
    "next_due_date": 60, "status": 50, "risk_level": 45, "missed_count": 45,
}


def _filter_by_date_range(rows, start_date, end_date):
    """Filter rows whose sip_start_date falls within [start_date, end_date]."""
    if not start_date and not end_date:
        return rows
    fmt = "%d-%m-%Y"
    start = datetime.strptime(start_date, fmt) if start_date else datetime.min
    end = datetime.strptime(end_date, fmt) if end_date else datetime.max
    out = []
    for r in rows:
        d = datetime.strptime(r["sip_start_date"], fmt)
        if start <= d <= end:
            out.append(r)
    return out


def generate_excel_report(rows: list, filename: str) -> str:
    df = pd.DataFrame(rows)[REPORT_COLUMNS].rename(columns=COLUMN_LABELS)
    path = os.path.join(OUTPUT_DIR, filename)
    df.to_excel(path, index=False)
    return path


def generate_pdf_report(rows: list, filename: str, title: str) -> str:
    path = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(
        path,
        pagesize=landscape(A4),
        leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        "cell", parent=styles["Normal"], fontSize=7.5, leading=9, wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "header", parent=cell_style, textColor=colors.white, fontName="Helvetica-Bold",
    )
    elements = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    table_data = [[Paragraph(COLUMN_LABELS[c], header_style) for c in REPORT_COLUMNS]]
    for r in rows:
        table_data.append([Paragraph(str(r[c]), cell_style) for c in REPORT_COLUMNS])

    col_widths = [COLUMN_WIDTHS[c] for c in REPORT_COLUMNS]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D9E75")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1EFE8")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(table)
    doc.build(elements)
    return path


def build_report(rows, scope: str, fmt: str, start_date=None, end_date=None) -> str:
    """
    scope: used only to name the file (e.g. 'individual_UCC1001', 'combined_all',
           'branch_XXXX', 'scheme_Axis_Midcap_Fund')
    fmt: 'excel' or 'pdf'
    """
    rows = _filter_by_date_range(rows, start_date, end_date)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "excel":
        filename = f"{scope}_{timestamp}.xlsx"
        return generate_excel_report(rows, filename)
    elif fmt == "pdf":
        filename = f"{scope}_{timestamp}.pdf"
        return generate_pdf_report(rows, filename, title=f"SIP Report - {scope}")
    else:
        raise ValueError("format must be 'excel' or 'pdf'")
