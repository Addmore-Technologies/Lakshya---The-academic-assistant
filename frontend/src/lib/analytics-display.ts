export interface CoScoreValue {
  co_number: number;
  marks: number;
  max: number;
  percentage: number | null;
}

export interface CoResultRow {
  coNumber: number;
  score: CoScoreValue | null;
}

/** Preserve every subject CO and represent missing quiz coverage as unassessed. */
export function buildCoResultRows(
  outcomeNumbers: readonly number[],
  scores: readonly CoScoreValue[],
): CoResultRow[] {
  const byNumber = new Map(scores.map((score) => [score.co_number, score] as const));
  return outcomeNumbers.map((coNumber) => ({
    coNumber,
    score: byNumber.get(coNumber) ?? null,
  }));
}

/** Average only actual numeric attainment values; never turn missing values into zero. */
export function averageAssessedPercentages(values: readonly (number | null | undefined)[]): number | null {
  const assessed = values.filter((value): value is number => value !== null && value !== undefined && Number.isFinite(value));
  if (!assessed.length) return null;
  return Math.round(assessed.reduce((sum, value) => sum + value, 0) / assessed.length);
}
