"""End-to-end tests for the fill pipeline. Run: pytest -q"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import os
os.environ.setdefault("API_KEY", "test-key")

from app.field_mapper import build_field_values, load_mapping
from app.main import app
from app.models import Broker, Financials, Party, PropertyInfo, Transaction
from app.pdf_filler import fill_pdf, list_fields

BASE = Path(__file__).resolve().parent.parent
TEMPLATE = BASE / "templates" / "commission_worksheet.pdf"
MAPPING = BASE / "mappings" / "commission_fields.json"

client = TestClient(app)


def sample_txn() -> Transaction:
    return Transaction(
        transaction_type="Lease",
        property_type="Office",
        landlord=Party(company="Douglas Emmett 2008, LLC", city="Santa Monica", state="CA"),
        tenant=Party(company="BINA.CX LLC", first_name="Eylon Leo", last_name="Cooper"),
        property=PropertyInfo(address="16000 Ventura Boulevard", suite="520", rentable_sf=1875),
        financials=Financials(rate_per_sf=2.65, rent_type="FSG"),
        lease_term_months=12,
        listing_broker=Broker(name="David Kaufman", company="Lee & Associates"),
    )


def test_template_exists():
    assert TEMPLATE.exists()


def test_mapping_produces_values():
    mapping = load_mapping(MAPPING)
    values, _ = build_field_values(sample_txn(), mapping)
    assert values["Text21"] == "BINA.CX LLC"          # tenant company
    assert values["Text47"] == "$2.65"                 # rate/SF
    assert values["Text48"] == "1,875"                 # premises SF
    assert values["Combo Box4"] == "Lease"             # transaction type
    assert values["Check Box1"] == "/Yes"              # NEW box via _constants


def test_fill_writes_values(tmp_path):
    mapping = load_mapping(MAPPING)
    values, _ = build_field_values(sample_txn(), mapping)
    out = tmp_path / "out.pdf"
    result = fill_pdf(TEMPLATE, values, out, flatten=False)
    assert not result["missing"]
    readback = list_fields(out)
    assert readback["Text21"]["value"] == "BINA.CX LLC"


def test_api_requires_key():
    r = client.post("/fill-commission-worksheet", json={"transaction": {"tenant": {"name": "X"}}})
    assert r.status_code == 401


def test_api_fills_and_returns_url():
    r = client.post(
        "/fill-commission-worksheet",
        headers={"X-API-Key": "test-key"},
        json={"transaction": sample_txn().model_dump()},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fields_filled"] >= 6
    assert body["download_url"].endswith(".pdf")
    d = client.get(f"/download/{body['filename']}")
    assert d.status_code == 200
    assert d.headers["content-type"] == "application/pdf"


def test_inspect_and_fill_by_fields():
    with open(TEMPLATE, "rb") as f:
        r = client.post(
            "/inspect-template",
            headers={"X-API-Key": "test-key"},
            files={"file": ("ws.pdf", f, "application/pdf")},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["field_count"] > 100
    assert body["labeled"] > body["field_count"] * 0.8
    token = body["template_token"]

    r2 = client.post(
        "/fill-by-fields",
        headers={"X-API-Key": "test-key"},
        json={"template_token": token, "values": {"Text21": "BINA.CX LLC", "Combo Box4": "Lease"}},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["fields_filled"] == 2


def test_download_blocks_traversal():
    r = client.get("/download/..%2f..%2fapp%2fmain.py")
    assert r.status_code == 404
