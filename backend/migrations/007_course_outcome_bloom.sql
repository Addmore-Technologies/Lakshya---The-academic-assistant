-- Add Bloom taxonomy metadata to course outcomes.
-- Existing records remain unchanged.

ALTER TABLE course_outcomes
ADD COLUMN IF NOT EXISTS bloom_level integer;

ALTER TABLE course_outcomes
ADD COLUMN IF NOT EXISTS bloom_name text;

-- Restrict Bloom levels to the standard six levels.
ALTER TABLE course_outcomes
DROP CONSTRAINT IF EXISTS course_outcomes_bloom_level_check;

ALTER TABLE course_outcomes
ADD CONSTRAINT course_outcomes_bloom_level_check
CHECK (bloom_level BETWEEN 1 AND 6);

-- Restrict taxonomy names to recognized values.
ALTER TABLE course_outcomes
DROP CONSTRAINT IF EXISTS course_outcomes_bloom_name_check;

ALTER TABLE course_outcomes
ADD CONSTRAINT course_outcomes_bloom_name_check
CHECK (
    bloom_name IN (
        'Remembering',
        'Understanding',
        'Applying',
        'Analyzing',
        'Evaluating',
        'Creating'
    )
);
