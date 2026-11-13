# Arya faculty workflow implementation handoff

## Implemented in this delivery

### Subject CO setup (R1)
- Added a subject-level CO1–CO6 editor to the faculty upload page.
- Descriptions, threshold percentages and target-attainment percentages are saved through the existing authenticated `PUT /subjects/{id}/cos` API.
- The editor checks missing descriptions, duplicate CO numbers and percentage bounds; it also reports missing/duplicate numbers already returned by the API.
- COs are configured once per subject and are not requested during module upload.

### Module upload (R2)
- Updated the picker to show `.pptx` and `.pdf`, file size validation (25 MB), module number/title, progress and error states.
- Removed all manual CO selection from module upload.
- After the backend's `202`, the UI says the upload was accepted and polls `/modules/{id}/status` while pending/processing. It does not announce processing completion until the API reports it.
- The existing backend contract currently accepts `.pptx` only. PDF selection is therefore blocked with an explicit explanation rather than sent to an endpoint that will reject it. Enable PDF parsing in the backend before removing this guard.

### CO coverage evidence (R3)
- Added authenticated `GET /modules/{id}/chunks`.
- The endpoint returns slide number, extracted text, tag status, all linked CO numbers and stored confidence.
- Faculty can inspect individual slide evidence and see unmatched slides.
- Subject coverage displays zero-evidence COs explicitly.
- UI clarifies that confidence is not attainment.
- The database does not record explicit-label versus AI-inferred provenance. The UI labels the existing stored matches as AI-inferred and does not claim explicit labels were distinguished.
- There is no correction endpoint in the current backend contract, so durable incorrect-tag flagging is not implemented yet.

### Question review (R4)
- Added module filtering alongside existing CO, source and review-status filters.
- Added a working edit flow using authenticated `PATCH /questions/{id}` for question text, four options, correct answer and explanation.
- Normalized backend lowercase statuses for the existing UI's title-case status chips and filters.
- Quiz Builder now prevents publishing if the current selected question set is not entirely present and approved in the current question bank.
- Regeneration is not exposed by the current API contract; the UI says it is unavailable rather than showing a fake success.
- Exact slide/page provenance is not part of the current question response schema; the review UI discloses that it is not supplied.

## Files changed
- `frontend/src/routes/faculty.upload.tsx`
- `frontend/src/routes/faculty.review.tsx`
- `frontend/src/routes/faculty.quiz-builder.tsx`
- `frontend/src/lib/api.ts`
- `backend/app/pg/chunks.py`
- `backend/app/routers/upload.py`
- `docs/api-contract.md`
- `docs/arya-integration-notes.md`

## API handoff items for Aparna
1. Enable PDF parsing and update `POST /modules/{id}/upload` contract (currently `.pptx` only).
2. Add a durable incorrect-tag correction endpoint, including whether a faculty correction replaces or supplements AI tags.
3. Add tag provenance (`explicit` vs `ai`) if explicit labels in uploaded material need a distinct visual treatment.
4. Add authenticated question regeneration contract and request/response shape.
5. Include source slide/page identifiers in generated question records/responses.

## Verification
- Python `compileall` passed for the backend source.
- Focused backend unit tests passed: 6 tests (`test_module_status.py` + `test_module_chunks_detail.py`).
- Frontend build/typecheck and pytest could not be completed in this environment:
  - `frontend/node_modules` was absent and offline npm install failed because the package tarballs were not cached.
  - The broader backend integration test collection is blocked because the environment lacks the `bcrypt` dependency; the focused unit tests listed above pass.
- No live backend/database/browser integration was run. Install project dependencies and run the normal CI checks before merging.
