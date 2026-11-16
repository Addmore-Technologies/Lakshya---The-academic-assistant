import type { Question } from "@/lib/api";

/** Keep quiz composition scoped to the module selected by the faculty member. */
export function filterQuestionsForModule(
  questions: Question[],
  moduleId: string,
): Question[] {
  if (!moduleId) return [];
  return questions.filter((question) => question.module_id === moduleId);
}

/** Validate the backend-owned question records before creating a quiz draft. */
export function validateQuizQuestionSet(
  questions: Question[],
  moduleId: string,
  approvedCourseOutcomeIds: string[],
): string | null {
  if (!moduleId) return "Select a module first.";
  if (questions.length === 0) return "Add at least one question to the quiz.";
  const coIds = new Set(approvedCourseOutcomeIds);

  if (questions.some((question) => question.module_id !== moduleId)) {
    return "Every quiz question must belong to the selected module.";
  }
  if (questions.some((question) => question.status.toLowerCase() !== "approved")) {
    return "Only approved questions can be added to a quiz.";
  }
  if (questions.some((question) => !question.co_id || !coIds.has(question.co_id))) {
    return "Every question must map to an approved Course Outcome in this subject.";
  }
  if (questions.some((question) => question.marks !== null && question.marks <= 0)) {
    return "Question marks must be greater than zero.";
  }
  return null;
}
