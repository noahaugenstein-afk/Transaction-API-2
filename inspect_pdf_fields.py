#!/usr/bin/env python3
"""Inspect a fillable PDF and print/save its AcroForm field ids.

This is the tool you run the moment you have your real Commission Worksheet.
It dumps every field id (e.g. Text102, Combo Box4) plus its type and current
value, and writes a starter mapping file you can fill in.

Usage:
    python tools/inspect_pdf_fields.py templates/commission_worksheet.pdf
    python tools/inspect_pdf_fields.py templates/commission_worksheet.pdf --starter mappings/commission_fields.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pypdf import PdfReader

# Friendly transaction paths the mapper understands — used to scaffold a starter map.
KNOWN_PATHS = [
    "transaction_type",
    "landlord.name", "landlord.company", "landlord.contact", "landlord.email",
    "landlord.phone", "landlord.address",
    "tenant.name", "tenant.company", "tenant.contact", "tenant.email",
    "tenant.phone", "tenant.address",
    "property.address", "property.suite", "property.city", "property.state",
    "property.zip", "property.rentable_sf",
    "financials.rate_per_sf", "financials.rent_type", "financials.monthly_rent",
    "financials.annual_rent", "financials.security_deposit", "financials.free_rent",
    "financials.ti_allowance", "financials.total_lease_consideration",
    "lease_commencement", "lease_expiration", "lease_term_months",
    "listing_broker.name", "listing_broker.company", "listing_broker.license_id",
    "listing_broker.commission_percent",
    "procuring_broker.name", "procuring_broker.company", "procuring_broker.license_id",
    "procuring_broker.commission_percent",
    "total_commission_percent", "total_commission_amount", "notes",
]

TYPE_LABELS = {"/Tx": "text", "/Btn": "checkbox/button", "/Ch": "choice", "/Sig": "signature"}


def inspect(pdf_path: Path) -> dict:
    reader = PdfReader(str(pdf_path))
    fields = reader.get_fields() or {}
    if not fields:
        print(
            f"\n  No AcroForm fields found in {pdf_path.name}.\n"
            "  The worksheet may be a flat/scanned PDF. If so, use the overlay\n"
            "  approach in the README (coordinate-based text placement) instead.\n",
            file=sys.stderr,
        )
    out = {}
    for name, f in fields.items():
        out[name] = {
            "type": TYPE_LABELS.get(str(f.get("/FT")), str(f.get("/FT"))),
            "current_value": f.get("/V"),
            "states": list(f["/_States_"]) if f.get("/_States_") else None,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path, help="Path to the fillable PDF")
    ap.add_argument(
        "--starter",
        type=Path,
        default=None,
        help="If given, write a starter mapping JSON to this path (with empty field ids to fill in).",
    )
    args = ap.parse_args()

    if not args.pdf.exists():
        print(f"File not found: {args.pdf}", file=sys.stderr)
        return 1

    fields = inspect(args.pdf)

    print(f"\nFound {len(fields)} AcroForm field(s) in {args.pdf.name}:\n")
    for name, info in sorted(fields.items()):
        extra = f"  states={info['states']}" if info["states"] else ""
        print(f"  {name:<28} {info['type']}{extra}")

    if args.starter:
        starter = {
            "_meta": {
                "template": args.pdf.name,
                "note": (
                    "Match each transaction path to one of the AcroForm field ids printed "
                    "above. Delete paths you don't need. A value can be a bare field id "
                    "string, or {\"field\": \"Text102\", \"format\": \"currency\"}."
                ),
                "available_field_ids": sorted(fields.keys()),
            },
            "fields": {path: "" for path in KNOWN_PATHS},
        }
        args.starter.parent.mkdir(parents=True, exist_ok=True)
        with open(args.starter, "w", encoding="utf-8") as fh:
            json.dump(starter, fh, indent=2)
        print(f"\nStarter mapping written to {args.starter}")
        print("Open it and paste the right field id next to each path.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
