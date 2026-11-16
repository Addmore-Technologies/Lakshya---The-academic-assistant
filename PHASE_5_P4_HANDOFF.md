# Lakshya — Phase 5 (P4) Handoff: Faculty Analytics & Excel Export

## Implemented in the frontend

- Reuses the existing faculty-authorized CO sheet, class summary, weak-CO, and Excel export endpoints.
- Supports subject, semester/module scope, and section filtering. Section options are populated from an unfiltered CO-sheet response; module scope waits for a module selection before requesting data.
- Displays student-wise CO percentages, total percentage, and assessed/not-assessed status in a horizontally scrollable table.
- Adds expandable student CO breakdown rows.
- Adds a CO-wise class summary showing attempted/enrolled counts, backend-configured threshold, target, average, and threshold status.
- Uses each CO's configured threshold for weak-score highlighting. Unassessed COs are not treated as weak or as zero.
- Score distribution excludes students with no assessed total.
- Module-level class summary is explicitly marked unavailable because the existing `/co-summary` and `/weak-cos` endpoints accept section but not module filters. Module CO sheet data and export remain supported.
- Excel download now reads the server's `Content-Disposition` filename when the header is exposed, with a subject-code fallback. Export has loading and error feedback.
- Analytics display helpers are covered by `frontend/src/test/analytics-display.test.ts`.

## Existing backend endpoints used

- `GET /subjects/{subject_id}/co-sheet?scope=semester|module&module_id=...&section=...`
- `GET /subjects/{subject_id}/co-summary?section=...`
- `GET /subjects/{subject_id}/weak-cos?section=...`
- `GET /subjects/{subject_id}/co-sheet/export?scope=...&module_id=...&section=...`

The module-level summary limitation is intentional; the frontend does not silently show semester attainment as module attainment. For browsers to read the server-provided filename, the backend CORS response must expose `Content-Disposition` (for example, `Access-Control-Expose-Headers: Content-Disposition`). If it is not exposed, the frontend falls back to the subject-code filename.

## Verification

- Static TypeScript/JSX parse check completed for touched files.
- Full `npm test` and `npm run build` still need to be run in the user's frontend environment because dependencies are not installed in this packaging environment.

## Manual acceptance checklist

- [ ] Switch between assigned subjects and confirm data stays subject-specific.
- [ ] Switch semester/module scope and select a module before data loads.
- [ ] Filter by available sections and clear the filter.
- [ ] Confirm unassessed COs show **Not assessed**, not 0% or weak.
- [ ] Expand a student row and inspect the CO breakdown.
- [ ] Confirm threshold/target values come from backend data.
- [ ] Export the current report and verify the downloaded `.xlsx` opens and matches the selected filters.
- [ ] Verify export loading and error states.
