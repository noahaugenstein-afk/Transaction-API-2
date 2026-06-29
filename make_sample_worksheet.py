#!/usr/bin/env python3
"""Generate a SAMPLE fillable Commission Worksheet so the pipeline is testable
before your real template is in place.

It writes templates/commission_worksheet.pdf with AcroForm fields whose ids match
the sample mapping in mappings/commission_fields.json. Replace this file with your
real worksheet later (and regenerate the mapping with inspect_pdf_fields.py).

Usage:
    python tools/make_sample_worksheet.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "templates" / "sample_worksheet.pdf"

# (label, acroform_field_id) laid out top to bottom.
ROWS = [
    ("Transaction Type", "f_txn_type"),
    ("Property Address", "f_prop_address"),
    ("Suite", "f_prop_suite"),
    ("Rentable SF", "f_prop_sf"),
    ("Landlord", "f_landlord"),
    ("Tenant", "f_tenant"),
    ("Lease Commencement", "f_commence"),
    ("Lease Expiration", "f_expire"),
    ("Term (months)", "f_term"),
    ("Rate / SF / Month", "f_rate"),
    ("Rent Type", "f_rent_type"),
    ("Monthly Rent", "f_monthly_rent"),
    ("Total Lease Consideration", "f_total_consideration"),
    ("Listing Broker", "f_listing_broker"),
    ("Procuring Broker", "f_procuring_broker"),
    ("Total Commission %", "f_comm_pct"),
    ("Total Commission $", "f_comm_amt"),
]


def build() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 72, "Commission Worksheet (SAMPLE)")
    c.setFont("Helvetica", 9)
    c.drawString(72, height - 88, "Replace with your real Lee & Associates worksheet template.")

    y = height - 130
    row_h = 30
    label_x = 72
    field_x = 240
    field_w = 280
    field_h = 18

    c.setFont("Helvetica", 10)
    form = c.acroForm
    for label, fid in ROWS:
        c.drawString(label_x, y + 4, f"{label}:")
        form.textfield(
            name=fid,
            x=field_x,
            y=y,
            width=field_w,
            height=field_h,
            borderWidth=0.5,
            borderColor=None,
            fillColor=None,
            textColor=None,
            forceBorder=True,
            fontSize=10,
        )
        y -= row_h

    c.showPage()
    c.save()
    print(f"Sample worksheet written to {OUT}")


if __name__ == "__main__":
    build()
