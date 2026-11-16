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
  it("supports fewer than six outcomes without requiring six", () => {
    expect(validateCourseOutcomeDraft([outcome(1, "Explain OS concepts")])).toBeNull();
  });

  it("renumbers outcomes sequentially after reordering", () => {
    const reordered = renumberCourseOutcomes([outcome(4, "Apply scheduling"), outcome(2, "Explain processes")]);
    expect(reordered.map((item) => item.number)).toEqual([1, 2]);
  });

  it("rejects blank descriptions and non-sequential numbering", () => {
    expect(validateCourseOutcomeDraft([outcome(1, " ")])).toMatch(/description/i);
    expect(validateCourseOutcomeDraft([outcome(2, "Explain OS concepts")])).toMatch(/sequential/i);
  });

  it("enforces the currently documented API maximum", () => {
    const tooMany = Array.from({ length: COURSE_OUTCOME_API_LIMIT + 1 }, (_, index) => outcome(index + 1, `Outcome ${index + 1}`));
    expect(validateCourseOutcomeDraft(tooMany)).toMatch(/at most/i);
  });
});
