-- Snapshot the verified source at generation time. Historical questions have no
-- evidence to backfill; leave both columns NULL. No quiz/attempt tables change.
ALTER TABLE public.questions
    ADD COLUMN IF NOT EXISTS source_slide_number integer,
    ADD COLUMN IF NOT EXISTS source_quote text;
