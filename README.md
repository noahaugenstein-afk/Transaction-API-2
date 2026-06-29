# Templates

`commission_worksheet.pdf` is the real LA North/Ventura Commission Worksheet,
already mapped in `mappings/commission_fields.json`. The API uses it by default.

To support another recurring form as a "known" template, drop its PDF here and run:

```bash
python tools/infer_field_labels.py templates/your_form.pdf            # see labels
python tools/inspect_pdf_fields.py templates/your_form.pdf --starter mappings/your_form.json
```

For one-off templates, don't add them here — use the runtime `/inspect-template`
+ `/fill-by-fields` flow instead.
