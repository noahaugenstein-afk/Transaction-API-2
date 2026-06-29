"""Infer a human-readable label for every AcroForm field in a PDF.

This is what lets the system fill ANY uploaded template, not just the known
Commission Worksheet. Opaque field ids (Text102) are paired with the printed
label nearest to them (to the left on the same row, else directly above), so a
caller — or an LLM — can match source data to fields by meaning.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

TYPE_LABELS = {"/Tx": "text", "/Btn": "checkbox", "/Ch": "choice", "/Sig": "signature"}


def _collect_widgets(reader: PdfReader) -> list[dict]:
    widgets = []
    for page_index, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        for ref in annots:
            obj = ref.get_object()
            if obj.get("/Subtype") != "/Widget":
                continue
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
                    "rect": [min(r[0], r[2]), min(r[1], r[3]), max(r[0], r[2]), max(r[1], r[3])],
                }
            )
    return widgets


def _page_words(pdf_path: Path):
    import pdfplumber

    pages_words, page_heights = [], []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            page_heights.append(float(page.height))
            pages_words.append(page.extract_words(use_text_flow=False, keep_blank_chars=False))
    return pages_words, page_heights


def _expand_label(seed, words) -> str:
    row = [
        w
        for w in words
        if abs(((w["top"] + w["bottom"]) / 2) - ((seed["top"] + seed["bottom"]) / 2)) <= 3
    ]
    row.sort(key=lambda w: w["x0"])
    phrase = []
    for w in row:
        if w["x0"] > seed["x1"] + 2:
            break
        if phrase and w["x0"] - phrase[-1]["x1"] > 30:
            phrase = []
        phrase.append(w)
    return " ".join(w["text"] for w in phrase) if phrase else seed["text"]


def _nearest_label(field_rect, words, page_height) -> str:
    fx0, fy0, fx1, fy1 = field_rect
    f_top = page_height - fy1
    f_bottom = page_height - fy0
    f_vcenter = (f_top + f_bottom) / 2

    best_left = best_above = None
    best_left_gap = best_above_gap = 1e9
    for w in words:
        wx0, wtop, wx1, wbottom = w["x0"], w["top"], w["x1"], w["bottom"]
        wv = (wtop + wbottom) / 2
        if abs(wv - f_vcenter) <= (f_bottom - f_top) * 0.8 + 4 and wx1 <= fx0 + 2:
            gap = fx0 - wx1
            if 0 <= gap < best_left_gap:
                best_left_gap, best_left = gap, w
        horiz_overlap = not (wx1 < fx0 - 2 or wx0 > fx1 + 2)
        if horiz_overlap and wbottom <= f_top + 2:
            gap = f_top - wbottom
            if 0 <= gap < best_above_gap:
                best_above_gap, best_above = gap, w

    if best_left is not None and best_left_gap <= 160:
        return _expand_label(best_left, words).strip(": ").strip()
    if best_above is not None and best_above_gap <= 40:
        return _expand_label(best_above, words).strip(": ").strip()
    if best_left is not None:
        return _expand_label(best_left, words).strip(": ").strip()
    return ""


def infer_labels(pdf_path: Path) -> list[dict]:
    reader = PdfReader(str(pdf_path))
    fields = reader.get_fields() or {}
    widgets = _collect_widgets(reader)
    pages_words, page_heights = _page_words(pdf_path)

    out = []
    for w in widgets:
        label = _nearest_label(w["rect"], pages_words[w["page"]], page_heights[w["page"]])
        entry = {"field_id": w["field_id"], "page": w["page"] + 1, "type": w["type"], "label": label}
        meta = fields.get(w["field_id"])
        if meta is not None and meta.get("/_States_"):
            entry["options"] = [s for s in meta["/_States_"] if s != "/Off"]
        out.append(entry)

    seen: dict[str, dict] = {}
    for e in out:
        if e["field_id"] not in seen or (not seen[e["field_id"]]["label"] and e["label"]):
            seen[e["field_id"]] = e
    return sorted(seen.values(), key=lambda e: (e["page"], e["field_id"]))
