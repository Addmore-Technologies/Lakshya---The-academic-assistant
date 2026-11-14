# Lakshya — Arya's Work Plan

**Role:** Frontend and faculty experience  
**Goal:** Make the upload → automatic CO coverage → question review journey intuitive, with no manual CO selection.

## Product rule
Faculty enter CO1–CO6 **once per subject**. During each module upload, faculty select subject, module number/title and PPTX/PDF only. AI identifies relevant COs using stored descriptions and any CO labels in the material. A page can map to multiple COs; unmatched content remains untagged for review.

## Tasks

### R1. Subject CO setup and editing
- Confirm the faculty can view/edit all six CO descriptions and targets for a subject.
- Display validation for missing/duplicate CO numbers; don't make faculty re-enter COs for each module.
- Coordinate existing `PUT /subjects/{id}/cos` usage with Aparna.

### R2. Module upload UI
- Update the existing faculty upload screen to accept `.pptx` and `.pdf` once Aparna enables the backend.
- Show file size/type limits, module number and title, upload progress, and clear errors.
- Remove any manual CO picker from module upload.
- After `202`, poll `GET /modules/{module_id}/status` until completion/failure; don't display success immediately.

### R3. AI CO coverage view
- Show each slide/page with its extracted heading/text excerpt, assigned CO1–CO6 tags, confidence (if returned), and source page/slide number.
- Show subject-level CO coverage counts and outcomes with no evidence.
- Make explicit CO labels and AI-inferred matches visually distinguishable if supported by the API.
- Provide a way for faculty to flag incorrect tags; coordinate correction endpoint with Aparna.
- Avoid presenting confidence as attainment percentage.

### R4. Question review interface
- Display generated questions as **drafts**, grouped/filterable by module, CO and review status.
- Show question type, options (for MCQ), answer, explanation and exact source slide/page.
- Implement edit, approve, reject and regenerate actions through authenticated backend routes.
- Disable publish until required review checks pass; make failed generation/retry visible.
- Use existing design system and preserve login/session handling.

### R5. Test states and responsive design
- Test no COs, no extractable text, AI not configured, partial tagging, empty question generation, long-running processing and server errors.
- Check desktop and mobile layouts, loading states, accessible labels and clear copy.
- Validate integration with Aparna's API contracts and Danwin's example AI outputs.

## Suggested branch and handoff
- Branch: `feature/arya-faculty-ai-workflow`
- Deliver screen mockups and expected API payloads to Aparna early.
- Use mocked responses until endpoints are ready; replace mocks before merging.

## Definition of done
- [ ] No CO selection in module upload
- [ ] PPTX/PDF upload UX and status polling
- [ ] Per-slide/page CO coverage and uncovered CO display
- [ ] Faculty question review/edit/approve/reject flow
- [ ] Loading, error, retry and empty states
- [ ] Responsive and authenticated frontend tested

## First action
Inspect the current faculty upload, CO coverage and question-review pages; sketch the revised flow and share API field requirements with Aparna.
