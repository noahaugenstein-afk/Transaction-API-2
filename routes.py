"""API endpoints exposed to the custom GPT Action (and any other client)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel as BaseModel_

from .auth import require_api_key
from .config import get_settings
from .field_mapper import build_field_values, load_mapping
from .models import FillRequest, FillResponse, Transaction
from .pdf_filler import fill_pdf
from .storage import (
    cleanup_expired,
    new_output_path,
    public_url_for,
    resolve_download,
    resolve_template_token,
)

router = APIRouter()


def _resolve_template_and_mapping(template_override: str | None):
    settings = get_settings()
    template_name = template_override or settings.default_template
    template_path = settings.templates_dir / template_name
    if not template_path.exists():
        raise HTTPException(
            status_code=400,
            detail=(
                f"Template '{template_name}' not found in templates/. "
                "Drop your Commission Worksheet PDF there and name it accordingly."
            ),
        )
    mapping_path = settings.mappings_dir / settings.default_mapping
    if not mapping_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Mapping '{settings.default_mapping}' not found in mappings/.",
        )
    return template_path, load_mapping(mapping_path)


def _do_fill(transaction: Transaction, template_override: str | None, flatten: bool) -> FillResponse:
    cleanup_expired()
    template_path, mapping = _resolve_template_and_mapping(template_override)
    values, unmapped = build_field_values(transaction, mapping)

    if not values:
        raise HTTPException(
            status_code=422,
            detail=(
                "No transaction fields matched the mapping. Either the mapping is still a "
                "placeholder or the transaction was empty. Unmapped paths with data: "
                f"{unmapped}"
            ),
        )

    out_path, _ = new_output_path()
    result = fill_pdf(template_path, values, out_path, flatten=flatten)

    settings = get_settings()
    return FillResponse(
        download_url=public_url_for(out_path.name),
        filename=out_path.name,
        expires_in_minutes=settings.output_ttl_minutes,
        fields_filled=len(result["filled"]),
        fields_skipped=result["missing"] + unmapped,
    )


@router.post("/fill-commission-worksheet", response_model=FillResponse, tags=["fill"])
async def fill_commission_worksheet(
    body: FillRequest, _: None = Depends(require_api_key)
) -> FillResponse:
    """Primary endpoint. The GPT extracts the lease itself, then POSTs structured
    transaction JSON here. Returns a download URL for the completed worksheet."""
    return _do_fill(body.transaction, body.template, body.flatten)


@router.post("/extract-and-fill", response_model=FillResponse, tags=["fill"])
async def extract_and_fill(
    file: UploadFile = File(...), _: None = Depends(require_api_key)
) -> FillResponse:
    """Optional one-shot endpoint: upload a lease PDF, the server extracts it with
    OpenAI and fills the worksheet. Requires EXTRACTION_ENABLED=true."""
    from .extractor import extract_transaction

    pdf_bytes = await file.read()
    try:
        transaction = extract_transaction(pdf_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return _do_fill(transaction, None, flatten=True)


@router.get("/download/{filename}", tags=["download"])
async def download(filename: str):
    """Serve a generated worksheet. No API key so the GPT can hand the user a clean
    link; filenames are unguessable UUIDs and expire on a TTL."""
    path = resolve_download(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="File not found or expired.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename="Commission Worksheet (completed).pdf",
    )


@router.get("/template-fields", tags=["introspection"])
async def template_fields(template: str | None = None, _: None = Depends(require_api_key)):
    """List the AcroForm field ids in a stored template."""
    from .pdf_filler import list_fields

    settings = get_settings()
    template_name = template or settings.default_template
    template_path = settings.templates_dir / template_name
    if not template_path.exists():
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found.")
    return {"template": template_name, "fields": list_fields(template_path)}


@router.post("/inspect-template", tags=["generic"])
async def inspect_template(
    file: UploadFile = File(...), _: None = Depends(require_api_key)
):
    """Upload ANY fillable PDF template. Returns a template_token plus every field
    with its inferred human-readable label, type, and (for dropdowns) options.

    The caller reads the labels, decides which source value goes in each field,
    then calls /fill-by-fields with the token and a {field_id: value} map. This is
    what lets the system fill templates it has never seen before."""
    from .field_labels import infer_labels
    from .storage import cache_uploaded_template, cleanup_expired_templates

    cleanup_expired_templates()
    pdf_bytes = await file.read()

    token = cache_uploaded_template(pdf_bytes)
    template_path = resolve_template_token(token)
    fields = infer_labels(template_path)
    labeled = sum(1 for f in fields if f["label"])
    return {
        "template_token": token,
        "field_count": len(fields),
        "labeled": labeled,
        "fields": fields,
        "note": (
            "Match each source value to a field by its label, then POST to "
            "/fill-by-fields with this template_token and {field_id: value}. For "
            "checkbox fields use the option value (often '/Yes'); for choice fields "
            "use one of the listed options exactly."
        ),
    }


class FillByFieldsRequest(BaseModel_):
    template_token: str
    values: dict
    flatten: bool = True


@router.post("/fill-by-fields", response_model=FillResponse, tags=["generic"])
async def fill_by_fields(body: "FillByFieldsRequest", _: None = Depends(require_api_key)):
    """Fill a previously-uploaded template (by token) with an explicit
    {field_id: value} map and return a download URL for the completed PDF."""
    from .storage import resolve_template_token

    cleanup_expired()
    template_path = resolve_template_token(body.template_token)
    if template_path is None:
        raise HTTPException(
            status_code=404,
            detail="template_token not found or expired. Call /inspect-template again.",
        )
    if not body.values:
        raise HTTPException(status_code=422, detail="No field values provided.")

    str_values = {k: ("" if v is None else str(v)) for k, v in body.values.items()}
    out_path, _token = new_output_path()
    result = fill_pdf(template_path, str_values, out_path, flatten=body.flatten)

    settings = get_settings()
    return FillResponse(
        download_url=public_url_for(out_path.name),
        filename=out_path.name,
        expires_in_minutes=settings.output_ttl_minutes,
        fields_filled=len(result["filled"]),
        fields_skipped=result["missing"],
    )
