#!/usr/bin/env python3
"""Associate each AcroForm field with the printed label nearest to it.

This is what makes "upload ANY template and auto-fill" work: opaque field ids
like Text102 become meaningful ("Tenant Company", "Rate/Sq. Ft.") by matching
each field's position on the page to the closest text label to its left or above.

Output: JSON list of {field_id, page, type, rect, label, options} that a human —
or an LLM — can use to map data to fields without knowing Adobe's internal names.

Usage:
    python tools/infer_field_labels.py templates/commission_worksheet_real.pdf labels.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import ArrayObject

TYPE_LABELS = {"/Tx": "text", "/Btn": "checkbox", "/Ch": "choice", "/Sig": "signature"}


def _collect_widgets(reader: PdfReader) -> list[dict]:
    """Return one entry per widget with field id, page index, and rect."""
    widgets = []
    for page_index, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        for ref in annots:
            obj = ref.get_object()
            if obj.get("/Subtype") != "/Widget":
                continue
            # Resolve field name, walking up to the parent for kids.
            name = obj.get("/T")
            ftype = obj.get("/FT")
            parent = obj.get("/Parent")
            while name is None and parent is not None:
                pobj = parent.get_object()
                name = pobj.get("/T")
                ftype = ftype or pobj.get("/FT")
                parent = pobj.get("/Parent")
            rect = obj.get("/Rect")
            if name is None or rect is None:
                continue
            r = [float(x) for x in rect]
            widgets.append(
                {
                    "field_id": str(name),
                    "page": page_index,
                    "type": TYPE_LABELS.get(str(ftype), str(ftype)),
                    # normalize rect to [x0, y0, x1, y1] with y0<y1
                    "rect": [min(r[0], r[2]), min(r[1], r[3]), max(r[0], r[2]), max(r[1], r[3])],
                }
            )
    return widgets


def _page_words(pdf_path: Path):
    """Per page: list of words with positions (top-left origin, y down)."""
    import pdfplumber

    pages_words = []
    page_heights = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            page_heights.append(float(page.height))
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            pages_words.append(words)
    return pages_words, page_heights


def _nearest_label(field_rect, words, page_height) -> str:
    """Find the label for a field: prefer text immediately to its LEFT on the same
    row; fall back to text directly ABOVE. Coordinates: pdfplumber uses top-left
    origin (y down); pypdf rect uses bottom-left origin (y up). Convert field rect
    to top-left space first."""
    fx0, fy0, fx1, fy1 = field_rect
    # Convert field y to top-down coordinates.
    f_top = page_height - fy1
    f_bottom = page_height - fy0
    f_vcenter = (f_top + f_bottom) / 2

    best_left = None
    best_left_gap = 1e9
    best_above = None
    best_above_gap = 1e9

    for w in words:
        wx0, wtop, wx1, wbottom = w["x0"], w["top"], w["x1"], w["bottom"]
        wv = (wtop + wbottom) / 2
        # Same row? vertical centers close.
        same_row = abs(wv - f_vcenter) <= (f_bottom - f_top) * 0.8 + 4
        if same_row and wx1 <= fx0 + 2:  # word ends at/left of field start
            gap = fx0 - wx1
            if 0 <= gap < best_left_gap:
                best_left_gap = gap
                best_left = w
        # Above? word bottom is above field top, horizontally overlapping.
        horiz_overlap = not (wx1 < fx0 - 2 or wx0 > fx1 + 2)
        if horiz_overlap and wbottom <= f_top + 2:
            gap = f_top - wbottom
            if 0 <= gap < best_above_gap:
                best_above_gap = gap
                best_above = w

    # Prefer a close left label; else a close above label.
    if best_left is not None and best_left_gap <= 160:
        # Gather the full left-side label by grabbing adjacent words on the same row.
        return _expand_label(best_left, words, direction="left").strip(": ").strip()
    if best_above is not None and best_above_gap <= 40:
        return _expand_label(best_above, words, direction="above").strip(": ").strip()
    if best_left is not None:
        return _expand_label(best_left, words, direction="left").strip(": ").strip()
    return ""


def _expand_label(seed, words, direction: str) -> str:
    """Join words that belong to the same label phrase as `seed`."""
    row = [
        w
        for w in words
        if abs(((w["top"] + w["bottom"]) / 2) - ((seed["top"] + seed["bottom"]) / 2)) <= 3
    ]
    row.sort(key=lambda w: w["x0"])
    # Take a run of words ending at seed (for left labels) allowing small gaps.
    phrase = []
    for w in row:
        if w["x0"] > seed["x1"] + 2:
            break
        if phrase and w["x0"] - phrase[-1]["x1"] > 30:
            phrase = []  # gap too big, restart the phrase
        phrase.append(w)
    return " ".join(w["text"] for w in phrase) if phrase else seed["text"]


def infer(pdf_path: Path) -> list[dict]:
    reader = PdfReader(str(pdf_path))
    fields = reader.get_fields() or {}
    widgets = _collect_widgets(reader)
    pages_words, page_heights = _page_words(pdf_path)

    out = []
    for w in widgets:
        label = _nearest_label(w["rect"], pages_words[w["page"]], page_heights[w["page"]])
        entry = {
            "field_id": w["field_id"],
            "page": w["page"] + 1,
            "type": w["type"],
            "label": label,
        }
        meta = fields.get(w["field_id"])
        if meta is not None and meta.get("/_States_"):
            entry["options"] = [s for s in meta["/_States_"] if s not in ("/Off",)]
        out.append(entry)
    # De-dup by field_id (multi-widget fields), keep first with a label.
    seen = {}
    for e in out:
        if e["field_id"] not in seen or (not seen[e["field_id"]]["label"] and e["label"]):
            seen[e["field_id"]] = e
    return sorted(seen.values(), key=lambda e: (e["page"], e["field_id"]))


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: infer_field_labels.py <pdf> [out.json]", file=sys.stderr)
        return 1
    pdf = Path(sys.argv[1])
    result = infer(pdf)
    labeled = sum(1 for e in result if e["label"])
    print(f"{len(result)} fields, {labeled} with an inferred label\n")
    for e in result:
        opts = f"  options={e['options']}" if e.get("options") else ""
        print(f"  p{e['page']} {e['field_id']:<14} {e['type']:<9} {e['label']!r}{opts}")
    if len(sys.argv) >= 3:
        Path(sys.argv[2]).write_text(json.dumps(result, indent=2))
        print(f"\nwritten to {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
