# Arya implementation handoff — 13 November 2026

## Delivered in this archive

- Subject CO setup/editing for CO1–CO6 in the faculty upload workflow, persisted with `PUT /subjects/{id}/cos`; client-side missing-description, range and duplicate-number validation.
- Module creation/selection and upload of `.pptx` and `.pdf` files, with a 25 MB client/server limit and server-side file signature validation.
- Background processing status polling, tagging/coverage summary, per-slide/page extracted text, CO matches and match confidence. Unmatched chunks remain visible for review.
- Authenticated question edit, approve and reject actions; filters for module, CO, source and review status.
- Quiz publish checks requiring selected questions to be approved.
- PDF text extraction using `pypdf`; page numbers use the existing `slide_number` field.
- Added parser tests for text extraction, blank/image-only pages and invalid PDF bytes.

## Verified in this workspace

- `PYTHONPATH=backend pytest -q tests/unit/test_pdf_parser.py tests/unit/test_pipeline.py tests/unit/test_ppt.py tests/unit/test_module_chunks_detail.py` — 35 passed.
- `python -m compileall -q backend/app` — passed.

## Not verified / remaining API dependencies

- Full backend suite could not collect in this workspace because `DATABASE_URL` is unset and `bcrypt` is not installed. Set up the project's normal virtual environment and required test services before running it.
- Frontend dependencies were not installed here; `npm ci --ignore-scripts` timed out. Run frontend tests/build/lint locally after dependency installation.
- No hosted Supabase/Render deployment test was run.
- Scanned/image-only PDF OCR is not implemented; those pages are reported as skipped.
- CO-tag correction endpoint is not present in the current backend contract.
- Tag provenance (explicit source label vs AI inference) is not stored in the current schema.
- Authenticated question regeneration endpoint is not present; the UI does not claim to regenerate questions.
- Real AI/Token Factory calls and mobile browser QA remain to be verified with team credentials/devices.

## Run locally

From the repository root:

```bash
# Backend (activate your existing .venv first)
pip install -r backend/requirements.txt
PYTHONPATH=backend pytest -q

# Frontend
cd frontend
npm ci
npm test
npm run build
npm run lint
```

Do not run seed commands against the shared database unless the team has explicitly approved it.
