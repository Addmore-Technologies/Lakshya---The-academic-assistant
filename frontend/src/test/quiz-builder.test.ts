import { describe, expect, it } from "vitest";
import type { Question } from "@/lib/api";
import { filterQuestionsForModule, validateQuizQuestionSet } from "@/lib/quiz-builder";

const question = (overrides: Partial<Question> = {}): Question => ({
  id: "q-1",
  module_id: "module-1",
  co_id: "co-1",
  co_number: 1,
  stem: "What is an operating system?",
  options: ["A", "B", "C", "D"],
  correct_option: 0,
  explanation: null,
  marks: 2,
  difficulty: "easy",
  bloom_level: "Remember",
  status: "approved",
  source: "faculty",
  created_by: null,
  ...overrides,
});

describe("quiz builder module and CO validation", () => {
  it("only returns questions for the selected module", () => {
    const bank = [
      question(),
      question({ id: "q-2", module_id: "module-2" }),
    ];
    expect(filterQuestionsForModule(bank, "module-1").map((item) => item.id)).toEqual(["q-1"]);
  });

  it("returns no questions when a module has not been selected", () => {
    expect(filterQuestionsForModule([question()], "")).toEqual([]);
  });

  it("requires a selected module and at least one question", () => {
    expect(validateQuizQuestionSet([], "", ["co-1"])).toContain("Select a module");
    expect(validateQuizQuestionSet([], "module-1", ["co-1"])).toContain("at least one");
  });

  it("rejects questions from a different module", () => {
    expect(
      validateQuizQuestionSet([question({ module_id: "module-2" })], "module-1", ["co-1"]),
    ).toContain("selected module");
  });

  it("rejects unapproved questions and invalid CO mappings", () => {
    expect(
      validateQuizQuestionSet([question({ status: "draft" })], "module-1", ["co-1"]),
    ).toContain("approved");
    expect(
      validateQuizQuestionSet([question({ co_id: "foreign-co" })], "module-1", ["co-1"]),
    ).toContain("approved Course Outcome");
  });

  it("rejects zero or negative marks", () => {
    expect(
      validateQuizQuestionSet([question({ marks: 0 })], "module-1", ["co-1"]),
    ).toContain("greater than zero");
  });

  it("accepts valid approved questions mapped to this subject", () => {
    expect(validateQuizQuestionSet([question()], "module-1", ["co-1"])).toBeNull();
  });
});
