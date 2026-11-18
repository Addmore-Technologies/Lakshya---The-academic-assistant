import { afterEach, expect, it, vi } from "vitest";
import { BASE_URL, teachingAssignments, type TeachingAssignment } from "@/lib/api";

const id = "class/A B";
const collection = `${BASE_URL}/teaching-assignments`;
const detail = `${collection}/class%2FA%20B`;
const assignment: TeachingAssignment = {
  id, subject_id: "sub-1", section: "A", active: true, status: "active",
  code: "CS101", subject_name: "Algorithms", semester: "3",
};

function respond(data: unknown, status = 200) {
  const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(Response.json(data, { status }));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

it("gets the class roster with enrollment timestamps", async () => {
  const roster = {
    teaching_assignment: assignment, total_students: 1,
    students: [{ student_id: "s1", name: "Student", usn: "USN1", section: "A", enrolled_at: "2026-01-01T09:00:00Z" }],
  } satisfies Awaited<ReturnType<typeof teachingAssignments.roster>>;
  const fetch = respond(roster);
  await expect(teachingAssignments.roster(id)).resolves.toEqual(roster);
  expect(fetch).toHaveBeenCalledWith(`${detail}/roster`, expect.objectContaining({ method: "GET" }));
});

it("preserves submitted answers and null fields on unfinished attempts", async () => {
  const unfinished = {
    attempt_id: "a1", quiz_id: "q1", quiz_title: "Quiz", student_id: "s1", student_name: "Student",
    usn: "USN1", subject_id: assignment.subject_id, teaching_assignment_id: id, section: "A",
    attempt_number: 1, total_score: null, max_score: null, started_at: null, submitted_at: null, answers: null,
  };
  const history = [unfinished, { ...unfinished, attempt_id: "a2", attempt_number: 2, total_score: 0,
    max_score: 2, started_at: "2026-01-02T09:00:00Z", submitted_at: "2026-01-02T09:10:00Z", answers: { question1: 0 },
  }] satisfies Awaited<ReturnType<typeof teachingAssignments.attempts>>;
  const fetch = respond(history);
  await expect(teachingAssignments.attempts(id)).resolves.toEqual(history);
  expect(fetch).toHaveBeenCalledWith(`${detail}/attempts`, expect.objectContaining({ method: "GET" }));
});

it("distinguishes zero attainment from a CO with no data", async () => {
  const attainment = {
    subject_id: assignment.subject_id, teaching_assignment_id: id,
    cos: [{ number: 1, description: "Apply algorithms", attainment_pct: 0 },
          { number: 2, description: "Compare algorithms", attainment_pct: null }],
  } satisfies Awaited<ReturnType<typeof teachingAssignments.attainment>>;
  const fetch = respond(attainment);
  await expect(teachingAssignments.attainment(id)).resolves.toEqual(attainment);
  expect(fetch).toHaveBeenCalledWith(`${detail}/attainment`, expect.objectContaining({ method: "GET" }));
});

afterEach(() => vi.unstubAllGlobals());

it("lists faculty assignments as an array", async () => {
  const fetch = respond([assignment]);
  await expect(teachingAssignments.list()).resolves.toEqual([assignment]);
  expect(fetch).toHaveBeenCalledWith(collection, expect.objectContaining({ method: "GET" }));
});
