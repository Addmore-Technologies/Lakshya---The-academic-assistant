# Phase 3 audit: teaching assignments, rosters and quiz history

**Decision:** No assignment-link repair is indicated by the database checked. All three enrollments matched active assignments, and the one attempt carried the same assignment as its current enrollment. That attempt had **no question snapshot**. Keep it as legacy history; the current question bank is not evidence of what the student saw.

## Verified counts — November 18, 2026 (UTC)

One repeatable-read, read-only transaction against the PostgreSQL target supplied by the environment. These are counts for that target and snapshot only, not a statement about every deployment. No student records, answers or snapshot contents were retrieved. No seed, migration or repair was run.

| Check | Count |
|---|---:|
| Assignments: total / active / archived | 6 / 6 / 0 |
| Enrollments: total / missing assignment / eligible for the attempt writer's class check | 3 / 0 / 3 |
| Enrollment links: dangling / wrong subject / wrong section / archived | 0 / 0 / 0 / 0 |
| Unlinked enrollments: no exact match / one active only / one archived only / multiple generations | 0 / 0 / 0 / 0 |
| Attempts: total / missing assignment / SQL NULL snapshot / missing both | 1 / 0 / 1 / 0 |
| Attempt links: dangling / wrong quiz subject / archived | 0 / 0 / 0 |
| Attempts: no current subject enrollment / assignment differs from existing enrollment | 0 / 0 |

The missing snapshot alone does not identify the writer or date of origin. The snapshot count tests SQL NULL, not JSON validity or completeness.

## Which relationship is authoritative?

- **Enrollment is subject membership.** `backend/migrations/001_init.sql` makes `(student_id, subject_id)` unique; `section` is a label (default `A`), not a class key. A quiz belongs to a subject. An attempt belongs to a student and quiz, unique by `(student_id, quiz_id, attempt_number)`; it has no direct enrollment FK.
- **Assignment identifies a class.** `backend/migrations/008_teaching_assignments_and_class_history.sql` permits one *active* assignment per exact `(subject_id, section)`, but archived assignments may reuse that pair. Faculty ownership comes through `subjects.faculty_user_id`. An assignment FK proves the assignment exists, not that subject, section or student membership agrees.
- **008 is additive, not a backfill.** Both assignment FKs are nullable, without defaults, with `ON DELETE SET NULL`; `quiz_attempts.question_snapshot` is nullable JSONB. Existing rows are not linked by applying 008. A physical assignment deletion can erase attribution; archiving changes status without clearing links. Neither a non-null FK nor the migration name guarantees immutable labels or snapshot contents.
- **History follows the recorded attempt, not today's roster.** `backend/app/routers/attempt_history.py` scopes student history to the caller's student ID and left-joins the assignment. A null link survives there but not in class history, which checks faculty ownership, the stored assignment ID and the quiz subject. The displayed section comes from the assignment as currently named. Similarly, `get_assignment_roster` requires both the enrollment's assignment and subject; an unlinked enrollment can exist without appearing on a class roster.

## Writer inventory

| Path in this tree | Behavior and operational consequence |
|---|---|
| `backend/app/routers/teaching_assignments.py`: `enroll_student_in_assignment`, `update_assignment`, `archive_assignment` | Enrollment takes subject, section and ID from an owned, active assignment. An existing subject enrollment yields a conflict, even if unlinked. A rename updates linked enrollment labels; archive preserves the ID for history. Neither operation assigns old null rows. |
| `backend/app/routers/roster.py`: `confirm_roster`, `_get_or_create_assignment` | Both CSV insert branches resolve or create an active exact subject/section assignment and write its ID. Already-enrolled students are skipped: reimport is not a repair. CSV trims section and defaults blanks to `A`; the assignment API uppercases input. Case variants can therefore produce distinct classes. |
| `backend/app/routers/attempts.py` → `backend/app/stores/postgres_quiz_store.py`: `_resolve_attempt_assignment`, `save_attempt` | A new attempt requires that student's enrollment for the quiz subject, an active linked assignment of that subject, and equal section labels; otherwise the resolver returns `403 NOT_ENROLLED`. The insert captures the ID and question snapshot together. The existing-attempt update replaces neither. `backend/app/services/quizzes.py` falls back to live questions when a snapshot is absent; later edits can affect legacy grading/review. |
| `seed/seed_data.py`: `generate_sql` (enrollment and attempt inserts); `seed/seed.py`: `build_sql` | The generated enrollment omits the assignment; the generated attempt omits assignment and snapshot. The runner consumes that SQL. Fresh seed rows can thus be unlinked **after** 008; rerunning the seed is not a backfill. |
| `tests/backend/conftest.py`, `tests/backend/test_constraints.py` | Direct SQL fixture/constraint inserts omit the new fields. Distinguish intentional legacy test cases from fixtures meant to exercise a successful modern attempt. These are not evidence about deployed rows. |

## Repeat the audit

Use only a preconfigured, environment-only PostgreSQL connection to the intended database and a role authorized to see the whole dataset. Do not load application settings or credential files, echo connection details, or run the seed/test suite to obtain counts. Use a short connection timeout, disable client startup scripts/prompts and stop on the first error. Run the entire block in one session. If unavailable, denied, timed out or missing the 008 schema, roll back/disconnect and report **no verifiable counts** rather than zeros or partial results. The row-security setting makes a policy-filtered scan fail rather than silently undercount.

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '4s';
SET LOCAL lock_timeout = '1s';
SET LOCAL idle_in_transaction_session_timeout = '6s';
SET LOCAL search_path = pg_catalog, public;
SET LOCAL row_security = off;

SELECT count(*) AS assignments,
       count(*) FILTER (WHERE status = 'active') AS active,
       count(*) FILTER (WHERE status = 'archived') AS archived
FROM public.teaching_assignments;

SELECT count(*) AS enrollments,
       count(*) FILTER (WHERE e.teaching_assignment_id IS NULL) AS unlinked,
       count(*) FILTER (WHERE e.teaching_assignment_id IS NOT NULL AND t.id IS NULL) AS dangling,
       count(*) FILTER (WHERE t.subject_id <> e.subject_id) AS wrong_subject,
       count(*) FILTER (WHERE t.section <> e.section) AS wrong_section,
       count(*) FILTER (WHERE t.status = 'archived') AS linked_archived,
       count(*) FILTER (WHERE t.subject_id = e.subject_id AND t.section = e.section
                         AND t.status = 'active') AS eligible_memberships
FROM public.enrollments e
LEFT JOIN public.teaching_assignments t ON t.id = e.teaching_assignment_id;

-- One row per unlinked enrollment before counting. Include archived generations.
WITH candidates AS (
  SELECT e.id, count(t.id) AS n, count(t.id) FILTER (WHERE t.status = 'active') AS active
  FROM public.enrollments e
  LEFT JOIN public.teaching_assignments t ON t.subject_id = e.subject_id AND t.section = e.section
  WHERE e.teaching_assignment_id IS NULL
  GROUP BY e.id
)
SELECT count(*) FILTER (WHERE n = 0) AS no_match,
       count(*) FILTER (WHERE n = 1 AND active = 1) AS one_active_only,
       count(*) FILTER (WHERE n = 1 AND active = 0) AS one_archived_only,
       count(*) FILTER (WHERE n > 1) AS multiple_generations
FROM candidates;

SELECT count(*) AS attempts,
       count(*) FILTER (WHERE a.teaching_assignment_id IS NULL) AS unlinked,
       count(*) FILTER (WHERE a.question_snapshot IS NULL) AS no_snapshot,
       count(*) FILTER (WHERE a.teaching_assignment_id IS NULL AND a.question_snapshot IS NULL) AS missing_both,
       count(*) FILTER (WHERE a.teaching_assignment_id IS NOT NULL AND t.id IS NULL) AS dangling,
       count(*) FILTER (WHERE t.subject_id <> q.subject_id) AS wrong_subject,
       count(*) FILTER (WHERE t.status = 'archived') AS linked_archived,
       count(*) FILTER (WHERE e.id IS NULL) AS no_current_enrollment,
       count(*) FILTER (WHERE a.teaching_assignment_id IS NOT NULL AND e.id IS NOT NULL
                         AND a.teaching_assignment_id IS DISTINCT FROM e.teaching_assignment_id) AS differs_from_current
FROM public.quiz_attempts a
JOIN public.quizzes q ON q.id = a.quiz_id
LEFT JOIN public.teaching_assignments t ON t.id = a.teaching_assignment_id
LEFT JOIN public.enrollments e ON e.student_id = a.student_id AND e.subject_id = q.subject_id;

ROLLBACK;
```

The candidate buckets partition **only unlinked enrollments**. All other diagnostic columns can overlap; do not add them. An archived attempt link or disagreement with today's enrollment is a review signal, not proof of corruption. `eligible_memberships` checks class membership only, not quiz publication, timing or attempt limits.

## Proposed remediation (not executed)

1. **Stop creating gaps first.** Update the seed generator and ordinary integration fixtures in a separate change to establish assignments before enrollments and use the same attempt-capture rules as the application. Retain explicit legacy fixtures. Agree on one section-normalization rule before merging any case variants. Test both roster branches, duplicate subject enrollment, archive/recreate and rename.
2. **Triage enrollments before attempts.** If nulls appear, use the candidate buckets above. An exact, single active match is a candidate only after the roster owner verifies membership. Missing, archived-only, conflicting or reused labels need roster evidence; do not create a default section or choose the latest assignment to make the counts pass.
3. **Preserve historical uncertainty.** Link an old attempt only with evidence of that student's class for the quiz subject **at `started_at`** (for example a dated roster with a verified class identity). A current enrollment, even a unique one, is insufficient. Preserve existing links through archive/transfer. Keep missing snapshots null unless an authoritative question version from attempt start exists; flag legacy review instead of manufacturing a snapshot or regrading.
4. **Gate any future repair.** Require separate approval, a restorable backup, a dry-run count by evidence class and a rollback plan. Limit changes to reviewed rows still missing the intended field; preserve attempts, scores and answers. Rerun these aggregates and check student/owner history isolation and legacy fallback. Do not impose blanket `NOT NULL` while legacy rows or `ON DELETE SET NULL` semantics remain supported.
