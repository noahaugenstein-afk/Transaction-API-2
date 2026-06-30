"""Fills AcroForm (fillable) PDF fields using pypdf.

Handles text fields, checkboxes, and choice/dropdown fields. Optionally flattens
the result so the values become non-editable (good for sharing a finished worksheet).
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject


def list_fields(pdf_path: Path) -> dict[str, dict]:
    """Return a dict of {field_id: {type, value, states}} for every AcroForm field."""
    reader = PdfReader(str(pdf_path))
    fields = reader.get_fields() or {}
    out: dict[str, dict] = {}
    for name, f in fields.items():
        ftype = f.get("/FT")
        entry = {
            "type": {
                "/Tx": "text",
                "/Btn": "button/checkbox",
                "/Ch": "choice",
                "/Sig": "signature",
            }.get(str(ftype), str(ftype)),
            "value": f.get("/V"),
        }
        states = f.get("/_States_")
        if states:
            entry["states"] = list(states)
        out[name] = entry
    return out


def fill_pdf(
    template_path: Path,
    values: dict[str, str],
    output_path: Path,
    flatten: bool = True,
) -> dict[str, list[str]]:
    """Fill `values` into the AcroForm at `template_path`, write to `output_path`.

    Returns {"filled": [...], "missing": [...]} where missing are requested field
    ids that don't exist in the template.
    """
    reader = PdfReader(str(template_path))
    writer = PdfWriter()
    writer.append(reader)

    existing = set((reader.get_fields() or {}).keys())
    requested = set(values.keys())
    missing = sorted(requested - existing)
    fillable = {k: v for k, v in values.items() if k in existing}

    # Ensure NeedAppearances so viewers render the values for text fields.
    try:
        writer.set_need_appearances_writer(True)
    except Exception:
        pass

    for page in writer.pages:
        writer.update_page_form_field_values(page, fillable)

    if flatten:
        _flatten_fields(writer)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as fh:
        writer.write(fh)

    return {"filled": sorted(fillable.keys()), "missing": missing}


def _flatten_fields(writer: PdfWriter) -> None:
    """Mark fields read-only so the filled values can't be edited downstream.

    This is a lightweight flatten: it sets the read-only flag on every widget
    rather than rasterizing, which keeps the file small and the text selectable.
    """
    for page in writer.pages:
        annots = page.get("/Annots")
        if not annots:
            continue
        for ref in annots:
            obj = ref.get_object()
            if obj.get("/Subtype") == "/Widget":
                ff = int(obj.get("/Ff", 0))
                obj[NameObject("/Ff")] = NumberObject(ff | 1)  # bit 1 = ReadOnly
