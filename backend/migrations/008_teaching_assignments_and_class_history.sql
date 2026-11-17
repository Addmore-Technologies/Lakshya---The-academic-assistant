-- Lakshya: teaching assignments and immutable quiz history
-- Designed for PostgreSQL.

CREATE TABLE IF NOT EXISTS teaching_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    section text NOT NULL DEFAULT 'A',
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT teaching_assignments_status_check
        CHECK (status IN ('active', 'archived'))
);

ALTER TABLE enrollments
    ADD COLUMN IF NOT EXISTS teaching_assignment_id uuid
    REFERENCES teaching_assignments(id) ON DELETE SET NULL;

ALTER TABLE quiz_attempts
    ADD COLUMN IF NOT EXISTS teaching_assignment_id uuid
    REFERENCES teaching_assignments(id) ON DELETE SET NULL;

ALTER TABLE quiz_attempts
    ADD COLUMN IF NOT EXISTS question_snapshot jsonb;

CREATE INDEX IF NOT EXISTS idx_teaching_assignments_subject
    ON teaching_assignments(subject_id);

CREATE INDEX IF NOT EXISTS idx_enrollments_teaching_assignment
    ON enrollments(teaching_assignment_id);

CREATE INDEX IF NOT EXISTS idx_quiz_attempts_teaching_assignment
    ON quiz_attempts(teaching_assignment_id);

CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student_started
    ON quiz_attempts(student_id, started_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_teaching_assignments_active_section
    ON teaching_assignments(subject_id, section)
    WHERE status = 'active';
