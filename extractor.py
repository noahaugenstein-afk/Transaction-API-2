"""OPTIONAL server-side extraction of a Transaction from a raw lease PDF.

This is OFF by default (EXTRACTION_ENABLED=false). The recommended design is to
let your custom GPT read the uploaded lease itself and POST structured JSON to
/fill-commission-worksheet — that avoids a second LLM call and is cheaper and
faster. This module exists for callers who want the API to do extraction too
(e.g. a non-GPT client, a Zapier/Make automation, or a batch job).
"""

from __future__ import annotations

import json

from .config import get_settings
from .models import Transaction

EXTRACTION_SYSTEM_PROMPT = """You extract structured data from commercial real-estate
documents (leases, LOIs, purchase agreements). Read the document text and return ONLY a
JSON object matching the provided schema. Use null for anything not stated. Do not guess
dollar amounts or dates that are not present. Prefer the Basic Lease Information / summary
section when one exists.
"""


def _extract_text(pdf_bytes: bytes) -> str:
    import io

    import pdfplumber

    chunks: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text() or "")
    return "\n".join(chunks)


def extract_transaction(pdf_bytes: bytes) -> Transaction:
    settings = get_settings()
    if not settings.extraction_enabled:
        raise RuntimeError("Server-side extraction is disabled (set EXTRACTION_ENABLED=true).")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    from openai import OpenAI

    text = _extract_text(pdf_bytes)
    schema = Transaction.model_json_schema()

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"JSON schema:\n{json.dumps(schema)}\n\n"
                    f"Document text:\n{text[:120000]}"
                ),
            },
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    return Transaction.model_validate_json(raw)
