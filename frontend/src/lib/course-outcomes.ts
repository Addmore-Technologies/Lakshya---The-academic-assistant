import type { ExtractedCourseOutcome } from "@/lib/api";

/** Current backend constraint; this is a maximum, not a required CO count. */
export const COURSE_OUTCOME_API_LIMIT = 6;

export function renumberCourseOutcomes(
  outcomes: ExtractedCourseOutcome[],
): ExtractedCourseOutcome[] {
  return outcomes.map((outcome, index) => ({ ...outcome, number: index + 1 }));
}

export function validateCourseOutcomeDraft(
  outcomes: ExtractedCourseOutcome[],
): string | null {
  if (outcomes.length !== COURSE_OUTCOME_API_LIMIT) {
    return `Every subject must have exactly ${COURSE_OUTCOME_API_LIMIT} Course Outcomes (CO1–CO6).`;
  }
  if (outcomes.some((outcome, index) => outcome.number !== index + 1 || !outcome.description.trim())) {
    return "Use sequential CO numbers starting at CO1 and add a description to every outcome.";
  }
  return null;
}
