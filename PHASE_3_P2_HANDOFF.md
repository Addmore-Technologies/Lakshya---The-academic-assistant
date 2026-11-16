# Lakshya — Phase 3 (P2) Handoff: Material Upload & CO-Aware Quiz Builder

## Scope completed in this frontend phase

### 1. Teaching material upload
- Reused the existing faculty module upload workflow.
- Kept the upload format aligned with the current backend contract: `.pptx` only.
- Added client-side 25 MB size validation to match `MAX_UPLOAD_BYTES` in `backend/app/routers/upload.py`.
- Tightened the file picker accept hint and clear stale upload errors when a new file is selected.
- Existing background processing, status polling, chunk review, and CO coverage views remain in place.

**Important backend contract:** the current upload endpoint rejects PDF/PPT and accepts only valid `.pptx` files up to 25 MB. Do not advertise PDF support until Aparna changes the backend parser and contract.

### 2. AI question generation
- Added a faculty-only generation panel to Question Review.
- The panel selects a module, approved Course Outcome, difficulty, and question count.
- Calls the existing authenticated `POST /agent/chat` endpoint; the server-side `generate_quiz` tool validates faculty ownership and writes generated questions as `draft` with source `AI`.
- Generation count is limited to 1–20 to match `ai/schemas/agent-tools.json`.
- The UI checks the returned tool-call status and refreshes the review list only after a successful `draft_review` tool call.
- The UI explains that a processed PPTX and CO-tagged slide content are prerequisites.
- Generated questions are never automatically approved or published.

**Backend dependencies:** AI runtime must be configured (Token Factory and generation model environment settings). The backend returns `NO_TAGGED_CONTENT` when the selected module has no slides tagged to the selected CO.

### 3. Question review
- Shows marks and Bloom level when returned by the backend.
- Allows faculty to edit question text, choices, correct answer, explanation, marks, and CO mapping.
- Uses the existing authorized `PATCH /questions/{id}` endpoint.
- Approve/reject remains on the existing endpoints.

### 4. Quiz builder
- Restricts the approved question bank to the selected module so a quiz cannot accidentally mix module questions.
- Clears the selection and saved-draft state when the module changes.
- Allows faculty to adjust each selected question's CO mapping and marks before creating/publishing.
- Saves mapping/marks changes through the existing question update endpoint.
- Blocks draft save/publish while mapping edits are unsaved.
- Validates that selected questions are approved, belong to the selected module, map to an approved CO in the selected subject, and have positive marks.

## Files changed
- `frontend/src/routes/faculty.upload.tsx`
- `frontend/src/routes/faculty.review.tsx`
- `frontend/src/routes/faculty.quiz-builder.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/quiz-builder.ts` (new)
- `frontend/src/test/quiz-builder.test.ts` (new)

## Verification to run locally

From `frontend/`:

```bash
npm ci
npm test
npm run build
```

New tests cover module isolation, missing module/questions, unapproved questions, invalid CO mapping, invalid marks, and valid question selection.

## Manual acceptance checklist
- [ ] Upload a valid `.pptx` smaller than 25 MB and verify processing status.
- [ ] Try a PDF or `.ppt` and verify the UI/server reject it clearly.
- [ ] Try a `.pptx` larger than 25 MB and verify client-side rejection.
- [ ] Wait for slide extraction and CO tagging to complete.
- [ ] Generate 1–20 questions for a CO that has tagged slide content.
- [ ] Confirm generated questions appear as AI drafts, not approved questions.
- [ ] Edit a generated question's text, choices, correct option, marks, and CO mapping.
- [ ] Approve the question.
- [ ] In Quiz Builder, select a module and confirm only that module's approved questions appear.
- [ ] Change a selected question's CO mapping and marks; save and verify they persist after refresh.
- [ ] Confirm pending unsaved mapping changes block quiz save/publish.
- [ ] Build a quiz using approved questions from the selected module and publish through the existing API.

## Explicit non-goals / ownership
- No backend, database, AI generation, tagging, or scoring logic was changed.
- No PDF material upload support was fabricated; current backend accepts PPTX only.
- No generated question is automatically approved or published.
- Backend contract/configuration changes remain with Aparna.
