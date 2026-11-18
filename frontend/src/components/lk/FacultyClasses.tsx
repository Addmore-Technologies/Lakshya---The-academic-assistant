import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { teachingAssignments, type TeachingAssignment } from "@/lib/api";
import { Btn, Card, CO, inputCls } from "@/components/lk/ui";

export function FacultyClasses({ subjectId }: { subjectId: string }) {
  const [selectedId, setSelectedId] = useState("");
  const assignments = useQuery({
    queryKey: ["teaching-assignments"],
    queryFn: () => teachingAssignments.list(),
  });
  const choices = assignments.data?.filter((item) => item.subject_id === subjectId) ?? [];
  const selected = choices.find((item) => item.id === selectedId);

  return (
    <Card title="Classes and sections" className="col-span-12">
      <p className="mb-4 text-sm text-muted-foreground">
        All sections share this subject’s Course Outcomes. Select a class to see only its students,
        quiz attempts and attainment.
      </p>
      {assignments.isError ? (
        <Retry
          message="Could not load teaching assignments."
          retry={() => void assignments.refetch()}
        />
      ) : assignments.isPending ? (
        <p role="status">Loading classes…</p>
      ) : choices.length === 0 ? (
        <p>No teaching assignments for this subject.</p>
      ) : (
        <>
          <label className="flex items-center gap-3">
            Class / section
            <select
              className={inputCls}
              value={selected?.id ?? ""}
              onChange={(event) => setSelectedId(event.target.value)}
            >
              <option value="">Choose a class</option>
              {choices.map((item) => (
                <option key={item.id} value={item.id}>
                  Section {item.section}
                  {item.status === "archived" ? ` (archived · ${item.id})` : ""}
                </option>
              ))}
            </select>
          </label>
          {selected && <ClassReport key={selected.id} assignment={selected} />}
        </>
      )}
    </Card>
  );
}

function Retry({ message, retry }: { message: string; retry: () => void }) {
  return (
    <div role="alert" className="flex items-center gap-3 text-sm">
      {message}{" "}
      <Btn variant="secondary" size="sm" onClick={retry}>
        Retry
      </Btn>
    </div>
  );
}

function ClassReport({ assignment }: { assignment: TeachingAssignment }) {
  const { id, subject_id } = assignment;
  const report = useQuery({
    queryKey: ["class-report", subject_id, id],
    queryFn: async () => {
      const [roster, attempts, attainment] = await Promise.all([
        teachingAssignments.roster(id),
        teachingAssignments.attempts(id),
        teachingAssignments.attainment(id),
      ]);
      if (
        roster.teaching_assignment.id !== id ||
        roster.teaching_assignment.subject_id !== subject_id ||
        attainment.teaching_assignment_id !== id ||
        attainment.subject_id !== subject_id ||
        attempts.some((row) => row.teaching_assignment_id !== id || row.subject_id !== subject_id)
      ) {
        throw new Error("Class report returned for the wrong assignment.");
      }
      return { roster, attempts, attainment };
    },
  });
  if (report.isError)
    return (
      <Retry
        message="Could not load the selected class report."
        retry={() => void report.refetch()}
      />
    );
  if (!report.data) return <p role="status">Loading class report…</p>;
  const { roster, attempts, attainment } = report.data;
  return (
    <div
      className="mt-5 grid gap-5 text-sm md:grid-cols-3"
      aria-label={`Section ${assignment.section} report`}
    >
      <section>
        <h4 className="font-semibold">Class roster ({roster.total_students})</h4>
        {roster.students.length ? (
          <ul className="mt-2 space-y-1">
            {roster.students.map((s) => (
              <li key={s.student_id}>
                <span>{s.name}</span> · {s.usn}
              </li>
            ))}
          </ul>
        ) : (
          <p>No students linked to this class.</p>
        )}
      </section>
      <section>
        <h4 className="font-semibold">Quiz attempts</h4>
        {attempts.length ? (
          <ul className="mt-2 space-y-2">
            {attempts.map((a) => (
              <li key={a.attempt_id}>
                <strong>{a.quiz_title}</strong> · {a.student_name} ({a.usn})
                <div>
                  Attempt {a.attempt_number} ·{" "}
                  {a.submitted_at
                    ? a.total_score == null || a.max_score == null
                      ? "Submitted"
                      : `${a.total_score}/${a.max_score}`
                    : "In progress"}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p>No quiz attempts linked to this class.</p>
        )}
      </section>
      <section>
        <h4 className="font-semibold">Class CO attainment</h4>
        {attainment.cos.length ? (
          <ul className="mt-2 space-y-2">
            {attainment.cos.map((co) => (
              <li key={co.number}>
                <CO n={co.number} /> {co.description} ·{" "}
                <strong>
                  {co.attainment_pct == null ? "Not assessed" : `${Math.round(co.attainment_pct)}%`}
                </strong>
              </li>
            ))}
          </ul>
        ) : (
          <p>No Course Outcomes saved for this subject.</p>
        )}
      </section>
    </div>
  );
}
