"""Render an invoice as a PDF (pure Python, no external binaries)."""
from __future__ import annotations

import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.billing import Invoice
from app.models.tenant import Tenant

_PRIMARY = colors.HexColor("#1f3a5f")
_MUTED = colors.HexColor("#6b7280")
_LINE = colors.HexColor("#e5e7eb")


def _money(value: Decimal | float | int | str, currency: str) -> str:
    return f"{Decimal(str(value or 0)):,.2f} {currency}"


def render_invoice_pdf(invoice: Invoice, tenant: Tenant, company: dict[str, str]) -> bytes:
    """Return the invoice as PDF bytes.

    :param company: keys name/address/email/phone/tax_id/bank_details/logo (logo = path).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice {invoice.number}",
        author=company.get("name", "SaaS Manager"),
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleX", parent=styles["Title"], textColor=_PRIMARY, fontSize=22, spaceAfter=4)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=_MUTED, leading=11)
    normal = styles["Normal"]
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=_PRIMARY, fontSize=12, spaceBefore=8, spaceAfter=4)

    story: list = []

    # Header: logo (optional) + company block + invoice identity
    left_cells: list = []
    logo_path = company.get("logo")
    if logo_path:
        try:
            left_cells.append(Image(logo_path, width=42 * mm, height=18 * mm, kind="proportional"))
            left_cells.append(Spacer(1, 4))
        except Exception:  # noqa: BLE001 - a missing logo must not break the invoice
            pass
    left_cells.append(Paragraph(f"<b>{company.get('name', '')}</b>", normal))
    for field in ("address", "email", "phone"):
        if company.get(field):
            left_cells.append(Paragraph(company[field].replace("\n", "<br/>"), small))
    if company.get("tax_id"):
        left_cells.append(Paragraph(f"Tax ID: {company['tax_id']}", small))

    right_block = [
        Paragraph("INVOICE", title_style),
        Paragraph(f"<b>{invoice.number}</b>", normal),
        Paragraph(f"Status: {invoice.status}", small),
        Paragraph(f"Issue date: {invoice.issue_date:%Y-%m-%d}", small),
        Paragraph(f"Due date: {invoice.due_date:%Y-%m-%d}", small),
    ]

    header = Table([[left_cells, right_block]], colWidths=[100 * mm, 74 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header)
    story.append(Spacer(1, 8 * mm))

    # Bill-to
    story.append(Paragraph("Billed to", h2))
    bill_to = [Paragraph(f"<b>{tenant.name}</b>", normal)]
    for line in (tenant.contact_name, tenant.email, tenant.phone, tenant.country, tenant.tax_id):
        if line:
            bill_to.append(Paragraph(line, small))
    story.append(bill_to[0])
    for line in bill_to[1:]:
        story.append(line)
    story.append(Spacer(1, 6 * mm))

    # Lines table
    rows = [["Description", "Qty", "Unit price", "Amount"]]
    for line in invoice.lines:
        rows.append([
            Paragraph(line.description, normal),
            f"{Decimal(str(line.quantity)):g}",
            _money(line.unit_price, invoice.currency),
            _money(line.line_total, invoice.currency),
        ])
    table = Table(rows, colWidths=[95 * mm, 18 * mm, 30 * mm, 31 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, _LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 4 * mm))

    # Totals
    totals_rows = [["Subtotal", _money(invoice.subtotal, invoice.currency)]]
    if invoice.discount_total:
        totals_rows.append(["Discount", f"- {_money(invoice.discount_total, invoice.currency)}"])
    if invoice.tax_total:
        totals_rows.append(["Tax", _money(invoice.tax_total, invoice.currency)])
    if invoice.late_fee:
        totals_rows.append(["Late fee", _money(invoice.late_fee, invoice.currency)])
    totals_rows.append(["Total", _money(invoice.total + invoice.late_fee, invoice.currency)])
    totals_rows.append(["Paid", _money(invoice.amount_paid, invoice.currency)])
    totals_rows.append(["Balance due", _money(invoice.balance, invoice.currency)])

    totals = Table(totals_rows, colWidths=[130 * mm, 44 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -3), (-1, -3), 0.5, _LINE),
        ("TEXTCOLOR", (0, -1), (-1, -1), _PRIMARY),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(totals)

    # Bank details / footer
    if company.get("bank_details"):
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("Payment details", h2))
        story.append(Paragraph(company["bank_details"].replace("\n", "<br/>"), small))
    if invoice.notes:
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(invoice.notes, small))

    doc.build(story)
    return buffer.getvalue()
