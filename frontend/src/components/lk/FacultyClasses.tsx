
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import {
  teachingAssignments,
  type TeachingAssignment,
} from "@/lib/api";
import { Btn, Card, CO, inputCls } from "@/components/lk/ui";

export function FacultyClasses({ subjectId }: { subjectId: string }) {
  const [selectedId, setSelectedId] = useState("");
  const [newSection, setNewSection] = useState("");
  const [editSection, setEditSection] = useState<string | null>(null);
  const [studentUsn, setStudentUsn] = useState("");
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [notice, setNotice] = useState("");
  const queryClient = useQueryClient();

  const assignments = useQuery({
    queryKey: ["teaching-assignments"],
    queryFn: () => teachingAssignments.list(),
  });

  const choices =
    assignments.data?.filter((item) => item.subject_id === subjectId) ?? [];

  const selected = choices.find((item) => item.id === selectedId);

  const refresh = async (id?: string) => {
    await queryClient.invalidateQueries({
      queryKey: ["teaching-assignments"],
    });
    if (id) {
      await queryClient.invalidateQueries({
        queryKey: ["class-report", subjectId, id],
      });
    }
  };

  const createClass = useMutation({
    mutationFn: (section: string) =>
      teachingAssignments.create(subjectId, section),
    onSuccess: async (created) => {
      setNewSection("");
      setSelectedId(created.id);
      setNotice(`Section ${created.section} created successfully.`);
      await refresh(created.id);
    },
  });

  const updateClass = useMutation({
    mutationFn: ({ id, section }: { id: string; section: string }) =>
      teachingAssignments.update(id, section),
    onSuccess: async (updated) => {
      setEditSection(null);
      setNotice(`Section updated to ${updated.section}.`);
      await refresh(updated.id);
    },
  });

  const archiveClass = useMutation({
    mutationFn: (id: string) => teachingAssignments.archive(id),
    onSuccess: async (result) => {
      setConfirmArchive(false);
      setEditSection(null);
      setNotice("Class archived successfully.");
      await refresh(result.id);
    },
  });

  const enrollStudent = useMutation({
    mutationFn: ({ id, usn }: { id: string; usn: string }) =>
      teachingAssignments.enrollStudent(id, usn),
    onSuccess: async () => {
      setStudentUsn("");
      setNotice("Student enrolled successfully.");
      if (selected) await refresh(selected.id);
    },
  });

  const handleCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const section = newSection.trim().toUpperCase();
    if (!subjectId || !section || section.length > 20) return;

    setNotice("");
    createClass.mutate(section);
  };

  const handleUpdate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected || selected.status !== "active") return;

    const section = (editSection ?? "").trim().toUpperCase();
    if (!section || section.length > 20) return;

    setNotice("");
    updateClass.mutate({ id: selected.id, section });
  };

  const handleEnroll = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected || selected.status !== "active") return;

    const usn = studentUsn.trim().toUpperCase();
    if (!usn) return;

    setNotice("");
    enrollStudent.mutate({ id: selected.id, usn });
  };

  const busy =
    createClass.isPending ||
    updateClass.isPending ||
    archiveClass.isPending ||
    enrollStudent.isPending;

  return (
    <Card title="Classes and sections" className="col-span-12">
      <p className="mb-4 text-sm text-muted-foreground">
        All sections share this subject's six Course Outcomes.
        Student rosters, quiz attempts and attainment are class-specific.
      </p>

      <form onSubmit={handleCreate} className="mb-5 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          New section
          <input
            className={inputCls}
            placeholder="e.g. A, B, CSE-A"
            maxLength={20}
            value={newSection}
            onChange={(event) => setNewSection(event.target.value)}
            disabled={busy}
            required
          />
        </label>
        <Btn type="submit" disabled={busy || !subjectId || !newSection.trim()}>
          {createClass.isPending ? "Creating..." : "Create Class"}
        </Btn>
      </form>

      {notice && <p role="status" className="mb-4 text-sm">{notice}</p>}

      {createClass.isError && (
        <p role="alert" className="mb-3 text-sm text-red-600">
          Could not create class. Check for an existing section or retry.
        </p>
      )}

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
          <label className="flex flex-col gap-1 text-sm">
            Class / section
            <select
              className={inputCls}
              value={selected?.id ?? ""}
              onChange={(event) => {
                setSelectedId(event.target.value);
                setEditSection(null);
                setStudentUsn("");
                setConfirmArchive(false);
                setNotice("");
              }}
              disabled={busy}
            >
              <option value="">Choose a class</option>
              {choices.map((item) => (
                <option key={item.id} value={item.id}>
                  Section {item.section}
                  {item.status === "archived" ? " (archived)" : ""}
                </option>
              ))}
            </select>
          </label>

          {selected && (
            <>
              <div className="mt-5 space-y-4">
                <h3 className="font-semibold">
                  Section {selected.section}
                  {selected.status === "archived" ? " — Archived" : ""}
                </h3>

                {selected.status === "active" && (
                  <>
                    <section className="space-y-2">
                      <h4 className="font-semibold text-sm">Edit section</h4>
                      {editSection === null ? (
                        <Btn
                          variant="secondary"
                          size="sm"
                          disabled={busy}
                          onClick={() => {
                            setEditSection(selected.section);
                            setConfirmArchive(false);
                          }}
                        >
                          Edit Class
                        </Btn>
                      ) : (
                        <form onSubmit={handleUpdate} className="flex flex-wrap gap-2">
                          <input
                            aria-label="Edit section name"
                            className={inputCls}
                            maxLength={20}
                            value={editSection}
                            onChange={(event) => setEditSection(event.target.value)}
                            disabled={busy}
                            required
                          />
                          <Btn
                            type="submit"
                            disabled={busy || !editSection.trim()}
                          >
                            {updateClass.isPending ? "Saving..." : "Save"}
                          </Btn>
                          <Btn
                            type="button"
                            variant="secondary"
                            disabled={busy}
                            onClick={() => setEditSection(null)}
                          >
                            Cancel
                          </Btn>
                        </form>
                      )}
                      {updateClass.isError && (
                        <p role="alert" className="text-sm text-red-600">
                          Could not update section. Check for duplicates.
                        </p>
                      )}
                    </section>

                    <section className="space-y-2">
                      <h4 className="font-semibold text-sm">Enroll student</h4>
                      <form onSubmit={handleEnroll} className="flex flex-wrap gap-2">
                        <input
                          aria-label="Student USN"
                          className={inputCls}
                          placeholder="Enter student USN"
                          value={studentUsn}
                          onChange={(event) => setStudentUsn(event.target.value)}
                          disabled={busy}
                          required
                        />
                        <Btn type="submit" disabled={busy || !studentUsn.trim()}>
                          {enrollStudent.isPending ? "Enrolling..." : "Enroll Student"}
                        </Btn>
                      </form>
                      <p className="text-xs text-muted-foreground">
                        The student must already exist in the system and
                        must not be enrolled in another section of this subject.
                      </p>
                      {enrollStudent.isError && (
                        <p role="alert" className="text-sm text-red-600">
                          Enrollment failed. Check the USN and whether the
                          student is already enrolled in this subject.
                        </p>
                      )}
                    </section>

                    <BulkStudentEnrollment key={selected.id} assignment={selected} />

                    <section className="space-y-2">
                      <h4 className="font-semibold text-sm">Archive class</h4>
                      {!confirmArchive ? (
                        <Btn
                          variant="secondary"
                          size="sm"
                          disabled={busy}
                          onClick={() => {
                            setConfirmArchive(true);
                            setEditSection(null);
                          }}
                        >
                          Archive Class
                        </Btn>
                      ) : (
                        <div className="space-y-2">
                          <p className="text-sm">
                            Archive Section {selected.section}? New enrollments
                            and section edits will be disabled.
                          </p>
                          <div className="flex gap-2">
                            <Btn
                              disabled={busy}
                              onClick={() => archiveClass.mutate(selected.id)}
                            >
                              {archiveClass.isPending ? "Archiving..." : "Confirm Archive"}
                            </Btn>
                            <Btn
                              variant="secondary"
                              disabled={busy}
                              onClick={() => setConfirmArchive(false)}
                            >
                              Cancel
                            </Btn>
                          </div>
                        </div>
                      )}
                      {archiveClass.isError && (
                        <p role="alert" className="text-sm text-red-600">
                          Could not archive class. Please retry.
                        </p>
                      )}
                    </section>
                  </>
                )}
              </div>

              <ClassReport key={selected.id} assignment={selected} />
            </>
          )}
        </>
      )}
    </Card>
  );
}

function BulkStudentEnrollment({
  assignment,
}: {
  assignment: TeachingAssignment;
}) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<
    Awaited<ReturnType<typeof teachingAssignments.bulkPreview>> | null
  >(null);
  const [result, setResult] = useState<
    Awaited<ReturnType<typeof teachingAssignments.bulkUpload>> | null
  >(null);
  const [error, setError] = useState("");

  const previewMutation = useMutation({
    mutationFn: (selectedFile: File) =>
      teachingAssignments.bulkPreview(assignment.id, selectedFile),
    onSuccess: (data) => {
      setPreview(data);
      setResult(null);
      setError("");
    },
    onError: (err) => {
      setPreview(null);
      setError(err instanceof Error ? err.message : "Preview failed");
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (selectedFile: File) =>
      teachingAssignments.bulkUpload(assignment.id, selectedFile),
    onSuccess: async (data) => {
      setResult(data);
      setPreview(null);
      setFile(null);
      setError("");

      await queryClient.invalidateQueries({
        queryKey: ["class-report", assignment.subject_id, assignment.id],
      });
    },
    onError: (err) =>
      setError(err instanceof Error ? err.message : "Enrollment failed"),
  });

  const busy = previewMutation.isPending || uploadMutation.isPending;

  const downloadCredentials = () => {
    if (!result?.credentials.length) return;

    const csv = [
      "USN,PIN",
      ...result.credentials.map((item) => `${item.usn},${item.pin}`),
    ].join("\r\n");

    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" })
    );

    const link = document.createElement("a");
    link.href = url;
    link.download = `student-credentials-${assignment.section}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="space-y-3 rounded-lg border p-4">
      <h4 className="font-semibold text-sm">
        Bulk student enrollment
      </h4>

      <p className="text-xs text-muted-foreground">
        Upload an Excel (.xlsx) or CSV (.csv) file with
        USN and Student Name columns. Maximum 5 MB.
      </p>

      <input
        aria-label="Upload student Excel or CSV"
        className={inputCls}
        type="file"
        accept=".xlsx,.csv"
        disabled={busy}
        onChange={(event) => {
          const selectedFile = event.target.files?.[0] ?? null;
          setFile(selectedFile);
          setPreview(null);
          setResult(null);
          setError("");

          if (selectedFile && selectedFile.size > 5 * 1024 * 1024) {
            setFile(null);
            setError("File must be 5 MB or smaller.");
          }
        }}
      />

      <Btn
        type="button"
        disabled={!file || busy}
        onClick={() => file && previewMutation.mutate(file)}
      >
        {previewMutation.isPending ? "Checking..." : "Preview Students"}
      </Btn>

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}

      {preview && (
        <div className="space-y-3">
          <p className="text-sm">
            Total: {preview.total_rows}
            {" | "}Ready: {preview.ready_count}
            {" | "}Skipped: {preview.skipped_count}
          </p>

          {preview.ready.length > 0 && (
            <div className="max-h-52 overflow-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr>
                    <th className="p-2">USN</th>
                    <th className="p-2">Student Name</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.ready.map((student) => (
                    <tr key={student.row} className="border-t">
                      <td className="p-2">{student.usn}</td>
                      <td className="p-2">{student.name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {preview.skipped.length > 0 && (
            <div className="text-sm">
              <strong>Skipped rows</strong>
              <ul className="list-disc pl-5">
                {preview.skipped.map((item, index) => (
                  <li key={index}>
                    Row {item.row}: {item.usn || "No USN"} — {item.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Btn
              type="button"
              disabled={busy || preview.ready_count === 0 || !file}
              onClick={() => file && uploadMutation.mutate(file)}
            >
              {uploadMutation.isPending
                ? "Enrolling..."
                : `Confirm Enrollment (${preview.ready_count})`}
            </Btn>

            <Btn
              type="button"
              variant="secondary"
              disabled={busy}
              onClick={() => {
                setPreview(null);
                setFile(null);
              }}
            >
              Cancel
            </Btn>
          </div>
        </div>
      )}

      {result && (
        <div role="status" className="space-y-2 text-sm">
          <p className="font-semibold">Enrollment completed</p>
          <p>
            Enrolled: {result.enrolled_students}
            {" | "}New accounts: {result.created_students}
            {" | "}Skipped: {result.skipped_count}
          </p>

          {result.credentials.length > 0 && (
            <div className="space-y-2">
              <p>
                Download initial PINs and distribute them securely.
                They will disappear when you leave this result.
              </p>
              <Btn
                type="button"
                variant="secondary"
                onClick={downloadCredentials}
              >
                Download Student Credentials
              </Btn>
            </div>
          )}

          {result.skipped.length > 0 && (
            <ul className="list-disc pl-5">
              {result.skipped.map((item, index) => (
                <li key={index}>
                  {item.usn || `Row ${item.row}`}: {item.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
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
        attempts.some(
          (row) =>
            row.teaching_assignment_id !== id ||
            row.subject_id !== subject_id
        )
      ) {
        throw new Error("Class report returned for the wrong assignment.");
      }

      return { roster, attempts, attainment };
    },
  });

  if (report.isError) {
    return (
      <Retry
        message="Could not load the selected class report."
        retry={() => void report.refetch()}
      />
    );
  }

  if (!report.data) return <p role="status">Loading class report…</p>;

  const { roster, attempts, attainment } = report.data;

  return (
    <div
      className="mt-5 grid gap-5 text-sm md:grid-cols-3"
      aria-label={`Section ${assignment.section} report`}
    >
      <section>
        <h4 className="font-semibold">
          Class roster ({roster.total_students})
        </h4>
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
                  {co.attainment_pct == null
                    ? "Not assessed"
                    : `${Math.round(co.attainment_pct)}%`}
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
