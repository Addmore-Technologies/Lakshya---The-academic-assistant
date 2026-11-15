# Lakshya — Phase 2 / P1 Course Outcomes Handoff

## Implemented in this phase

- Subject-scoped CO workflow remains on the existing `/faculty/upload` page and uses the signed-in faculty subject list.
- Shows approved/saved outcomes separately from an extracted draft.
- Displays the selected subject and source PDF filename.
- Validates PDF type and the backend's 10 MB limit before upload.
- Shows extraction progress, inline errors, and a retry action.
- Allows editing descriptions and Bloom taxonomy levels.
- Allows adding, removing, and reordering draft outcomes. Reordering renumbers the draft sequentially.
- Confirms before overwriting existing CO numbers and refreshes the subject detail/coverage queries after approval.
- Preserves existing attainment thresholds when updating matching CO numbers.
- Prevents approving an extraction result larger than the current backend save contract can support.

## Verified backend contract (from current repository source)

| Operation | Method and path | Verified behavior |
|---|---|---|
| Extract draft COs | `POST /subjects/{subject_id}/cos/extract` | Multipart field `file`; PDF only; 10 MB maximum; returns `subject_id`, `filename`, `cos`, `count`, `requires_review`, `saved` |
| List approved COs | `GET /subjects/{id}/cos` | Faculty ownership enforced; returns saved CO rows |
| Save/approve COs | `PUT /subjects/{id}/cos` | Body contains `cos` array; upserts by number; accepted CO numbers are 1–6 |
| Subject detail | `GET /subjects/{id}` | Returns subject metadata, saved COs, and modules; faculty ownership/student enrollment enforced |

## Backend dependencies for full P1 acceptance

The frontend does not modify backend code. The current backend source has these limitations that Aparna needs to address before the complete specification can be marked done:

1. Extraction accepts PDF only, not JPG/JPEG/PNG.
2. The CO upsert route validates CO numbers 1–6, so the current API cannot support an arbitrary number of outcomes. The UI does not assume every subject has exactly six; it follows the currently enforced API maximum.
3. The upsert route does not delete approved outcomes omitted from the submitted array. Removing a CO from the local draft therefore does not delete the saved record; the UI warns about this. A faculty-authorized delete/replace contract is required.
4. The API does not return upload timestamp or persisted extraction status/history. The UI can show the returned source filename but cannot invent those metadata.
5. The backend does not expose whether a CO is referenced by a quiz or a version/conflict mechanism. The UI confirms edits, but the backend must enforce safe replacement/versioning.
6. The upsert SQL uses `COALESCE` for Bloom fields, so the current API cannot clear an already-saved Bloom level by sending `null`; the UI preserves the prior value on save.

## Files changed

- `frontend/src/routes/faculty.upload.tsx`
- `frontend/src/lib/api.ts`
- `PHASE_2_P1_HANDOFF.md`

## Verification

The source ZIP is prepared from the Phase 1 package and includes all Phase 1 files. Dependency installation could not complete in the packaging environment, so Phase 2 `npm test` and `npm run build` have not been verified here. Run both from `frontend/` after extracting the ZIP.
