import { describe, expect, it } from "vitest";
import { averageAssessedPercentages, buildCoResultRows } from "@/lib/analytics-display";

describe("analytics display helpers", () => {
  it("keeps course outcomes with no quiz coverage as unassessed", () => {
    const rows = buildCoResultRows(
      [1, 2, 3],
      [{ co_number: 1, marks: 4, max: 5, percentage: 80 }],
    );
    expect(rows).toEqual([
      { coNumber: 1, score: { co_number: 1, marks: 4, max: 5, percentage: 80 } },
      { coNumber: 2, score: null },
      { coNumber: 3, score: null },
    ]);
  });

  it("does not convert missing attainment into zero", () => {
    expect(averageAssessedPercentages([null, undefined])).toBeNull();
    expect(averageAssessedPercentages([null, 80, 60])).toBe(70);
  });

  it("ignores non-finite values when averaging", () => {
    expect(averageAssessedPercentages([Number.NaN, 40, Number.POSITIVE_INFINITY])).toBe(40);
  });
});
