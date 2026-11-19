-- Permit unmapped questions during review. Existing mappings and quiz history stay intact.
ALTER TABLE questions ALTER COLUMN co_id DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'questions'::regclass AND conname = 'approved_question_requires_co') THEN
        ALTER TABLE questions ADD CONSTRAINT approved_question_requires_co
            CHECK (status <> 'approved' OR co_id IS NOT NULL);
    END IF;
END $$;
