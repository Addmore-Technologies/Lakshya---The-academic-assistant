# Arya faculty sprint — implementation handoff

## Scope completed in this update

- Faculty dashboard now includes real module navigation links and a per-CO coverage summary, with responsive dashboard cards.
- Module upload continues polling while status is `pending` or `processing`, then refreshes subject and coverage data when extraction finishes. The UI distinguishes successful extraction with unmatched chunks from a failed extraction.
- Added faculty-only `GET /modules/{module_id}/chunks` to expose extracted slide text and the highest-confidence CO tag for each chunk. The UI shows slide number, extracted text, matched CO or Unmatched, and tag confidence. Confidence is explicitly labelled as tag confidence, not attainment.
- Question review now normalizes API status/source casing, supports module and difficulty filters, has a working question editor backed by `PATCH /questions/{id}`, and displays loading/error/retry states. Bulk approval waits for API completion and reports failures rather than optimistically claiming success.
- Quiz builder starts with blank dates/title, requires an explicit module and title, validates that selected questions are still approved, shows selected marks and existing quizzes, and reuses a matching saved draft when retrying publish to avoid creating a new draft on every retry.
- Main faculty dashboard/upload/review/quiz layouts have responsive breakpoints.

## API contract addition

`GET /modules/{module_id}/chunks` (faculty only) returns:

```json
[
  {
    "chunk_id": "uuid",
    "slide_number": 1,
    "text": "Extracted slide text",
    "co_id": "uuid-or-null",
    "co_number": 1,
    "confidence": 0.93
  }
]
```

The endpoint returns the highest-confidence CO tag for each chunk. `co_id`, `co_number`, and `confidence` are null for unmatched chunks. It uses the existing `content_chunks` and `chunk_cos` tables; no migration is required. The endpoint checks module ownership through the existing faculty helpers.

## Verification status

- Production frontend build had passed on the user's machine with Vite 8.1.6 before this update.
- The latest uploaded archive does not contain `node_modules`, and this environment has no installed frontend dependencies. Therefore TypeScript, Vitest, ESLint, and a fresh Vite build could not be executed against these new changes here.
- Python source compilation is checked separately; full integration against the hosted PostgreSQL database and a real uploaded deck remains a team/demo verification step.
- Do not describe the new chunks endpoint as production-verified until tested against the deployed database and a real module.

## Required local verification

From the repository root:

```bash
python -m compileall -q backend
PYTHONPATH=backend pytest tests/unit -q
cd frontend
npm test
npx tsc --noEmit
npm run build
npm run lint
```

Then test the faculty flow with a real faculty account:
1. Open Faculty Dashboard and confirm module list and CO coverage load.
2. Upload a valid PPTX; confirm status polling continues through processing to done/failed.
3. Select the completed module and confirm slide text, CO tags, unmatched slides, and confidence appear.
4. Edit a draft question, save, approve/reject, and refresh to confirm persistence.
5. Build a quiz from approved questions, save a draft, publish, and confirm it appears under Existing quizzes.
6. Verify the faculty-only chunks endpoint rejects student access and a faculty user cannot inspect another faculty member's module.

## Known boundaries

- Upload currently supports `.pptx` only (25 MB max), as enforced by the backend contract. PDF upload was not added.
- The chunks endpoint displays one best-confidence CO tag per slide chunk; it does not expose every possible multi-tag association.
- The existing backend does not expose question regeneration from the faculty review screen as a direct endpoint in the current contract; generation remains dependent on the configured agent/runtime integration.
- Existing subject/CO management and quiz creation endpoints remain as already implemented; this update did not add new subject CRUD or a quiz-edit endpoint.
- A real hosted database/browser demo and pull-request review are still required.
