"""Translates the friendly Transaction model into the worksheet's AcroForm field names.

The mapping lives in mappings/<name>.json and looks like:

    {
      "_meta": {"template": "commission_worksheet.pdf"},
      "fields": {
        "tenant.name": "Text32",
        "tenant.company": "Text33",
        "property.address": "Text40",
        "property.rentable_sf": {"field": "Text102", "format": "number"},
        "financials.rate_per_sf": {"field": "Text111", "format": "currency"}
      }
    }

A mapping value can be either a bare AcroForm field id (string) or an object
with "field" plus an optional "format" hint (currency | number | percent | date).
You generate the left-hand paths automatically by running tools/inspect_pdf_fields.py
against your real worksheet, then matching each path to a field id.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Transaction


def load_mapping(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if "fields" not in data:
        raise ValueError(f"Mapping {path.name} is missing a top-level 'fields' object.")
    return data


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Turn a nested transaction dict into dotted paths -> scalar values."""
    flat: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            flat.update(_flatten(value, path))
    else:
        if obj is not None:
            flat[prefix] = obj
    return flat


def _format_value(value: Any, fmt: str | None) -> str:
    if value is None:
        return ""
    if fmt == "currency":
        try:
            return f"${float(value):,.2f}"
        except (TypeError, ValueError):
            return str(value)
    if fmt == "number":
        try:
            num = float(value)
            return f"{num:,.0f}" if num.is_integer() else f"{num:,}"
        except (TypeError, ValueError):
            return str(value)
    if fmt == "percent":
        try:
            return f"{float(value):g}%"
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def build_field_values(
    transaction: Transaction, mapping: dict[str, Any]
) -> tuple[dict[str, str], list[str]]:
    """Return (acroform_field -> string value) plus a list of paths that had data
    but no mapping entry (so you can see what still needs mapping)."""
    flat = _flatten(transaction.model_dump())
    field_map: dict[str, Any] = mapping["fields"]

    values: dict[str, str] = {}
    unmapped_with_data: list[str] = []

    for path, raw in flat.items():
        if path not in field_map:
            unmapped_with_data.append(path)
            continue
        spec = field_map[path]
        if isinstance(spec, dict):
            target = spec.get("field")
            fmt = spec.get("format")
        else:
            target, fmt = spec, None
        if not target:
            continue
        values[target] = _format_value(raw, fmt)

    # Apply any constant fields (e.g. always check the "NEW" box). Constants never
    # overwrite a value that came from the transaction data.
    for field_id, const_val in mapping.get("_constants", {}).items():
        values.setdefault(field_id, const_val)

    return values, sorted(unmapped_with_data)
