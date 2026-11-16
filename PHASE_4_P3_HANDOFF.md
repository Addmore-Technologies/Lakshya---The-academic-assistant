# Lakshya — Phase 4 (P3) Handoff: Student Quiz & Results UX

## Implemented in the frontend

- Preserved the existing student quiz list, explicit attempt start, answer autosave, resume-in-progress, submission confirmation, and answer review flows.
- Tracks the active quiz ID so the result screen can show the quiz title and subject.
- Displays the marks available for each question during an attempt.
- Displays backend-returned total earned/possible marks and guards the percentage display when maximum marks are zero.
- Shows per-CO earned/possible marks and percentage.
- Uses the subject's complete CO list to render **Not assessed** for outcomes not covered by the quiz; it does not turn missing scores into zero.
- Added tested `buildCoResultRows` helper in `frontend/src/lib/analytics-display.ts`.

## Backend contract blocker — refresh after submission

The existing `GET /attempts/{id}` response includes `status`, answers, and masked questions. When an attempt is submitted, it returns `status: "submitted"` but does **not** include the persisted grade. The current frontend therefore clears the stale in-progress attempt on refresh and cannot reconstruct the exact result without a new backend response.

Request to Aparna: extend `GET /attempts/{id}` for the owning student to include a `result` object when `status="submitted"`:

```json
{
  "result": {
    "total_score": 8,
    "max_score": 10,
    "co_scores": [
      { "co_number": 1, "marks": 5, "max": 5, "percentage": 100 },
      { "co_number": 2, "marks": 3, "max": 5, "percentage": 60 }
    ]
  }
}
```

The values must be read from persisted attempt and student-CO-score records, not recomputed in the browser. Keep the existing ownership check. Once this contract is available, the frontend can restore the result screen after refresh.

## Verification

- Added helper tests in `frontend/src/test/analytics-display.test.ts` for missing CO coverage and null-safe averages.
- Static TypeScript/JSX parse check completed for touched files. Full `npm test` and `npm run build` still need to be run in the user's frontend environment because dependencies are not installed in this packaging environment.

## Manual acceptance checklist

- [ ] Start a published quiz and verify title, subject, and question marks.
- [ ] Answer and refresh before submission; confirm the in-progress attempt resumes.
- [ ] Submit and verify confirmation, total marks, and per-CO marks.
- [ ] Confirm all subject COs appear and uncovered COs say **Not assessed**.
- [ ] Refresh after submission and verify the persisted result once the backend response enhancement is deployed.
- [ ] Review answers and retry only when attempts remain.
