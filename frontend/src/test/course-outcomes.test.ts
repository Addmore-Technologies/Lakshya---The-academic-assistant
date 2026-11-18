import { describe, expect, it } from "vitest";
import {
  COURSE_OUTCOME_API_LIMIT,
  renumberCourseOutcomes,
  validateCourseOutcomeDraft,
} from "@/lib/course-outcomes";
import type { ExtractedCourseOutcome } from "@/lib/api";

const outcome = (number: number, description: string): ExtractedCourseOutcome => ({
  number,
  description,
  bloom_level: null,
  bloom_name: null,
  threshold_pct: 60,
  target_attainment_pct: 60,
});

describe("course outcome draft helpers", () => {
  const six = Array.from({ length: 6 }, (_, index) => outcome(index + 1, `Outcome ${index + 1}`));

  it("accepts six completed outcomes", () => {
    expect(validateCourseOutcomeDraft(six)).toBeNull();
  });

  it("renumbers outcomes sequentially after reordering", () => {
    const reordered = renumberCourseOutcomes([outcome(4, "Apply scheduling"), outcome(2, "Explain processes")]);
    expect(reordered.map((item) => item.number)).toEqual([1, 2]);
  });

  it("rejects blank descriptions and non-sequential numbering", () => {
    expect(validateCourseOutcomeDraft([outcome(1, " "), ...six.slice(1)])).toMatch(/description/i);
    expect(validateCourseOutcomeDraft([outcome(2, "Explain OS concepts"), ...six.slice(1)])).toMatch(/sequential/i);
  });

  it("rejects both incomplete and oversized drafts", () => {
    expect(validateCourseOutcomeDraft(six.slice(1))).toMatch(/exactly 6/i);
    expect(validateCourseOutcomeDraft([...six, outcome(COURSE_OUTCOME_API_LIMIT + 1, "Extra")])).toMatch(/exactly 6/i);
  });
});
