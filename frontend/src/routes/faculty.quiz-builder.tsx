import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { GripVertical, Plus, Search, Send, X, Save } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { Shell } from "@/components/lk/Shell";
import { Btn, Card, Chip, CO, Field, inputCls, PageHead, type Status } from "@/components/lk/ui";
import { cn } from "@/lib/utils";
import { ApiError, questions, quizzes, subjects } from "@/lib/api";
import { getStoredSubjectId, storeSubjectId } from "@/lib/subject-context";
import { filterQuestionsForModule, validateQuizQuestionSet } from "@/lib/quiz-builder";
import type { Question, Quiz } from "@/lib/api";

export const Route = createFileRoute("/faculty/quiz-builder")({
  head: () => ({
    meta: [
      { title: "Quiz Builder · LAKSHYA" },
      { name: "description", content: "Build and publish quizzes from approved questions." },
      { property: "og:title", content: "Quiz Builder · LAKSHYA" },
      { property: "og:description", content: "A paper-planner for composing quizzes." },
    ],
  }),
  component: Page,
});

function Page() {
  const queryClient = useQueryClient();
  const [subjectId, setSubjectId] = useState<string | null>(() => getStoredSubjectId());
  const [quizTitle, setQuizTitle] = useState("");
  const [quizModule, setQuizModule] = useState<string>("");
  const [opensAt, setOpensAt] = useState("");
  const [closesAt, setClosesAt] = useState("");
  const [sel, setSel] = useState<string[]>([]);
  const [term, setTerm] = useState("");
  const [activeCO, setActiveCO] = useState<number | null>(null);
  const [drag, setDrag] = useState<number | null>(null);
  const [savedQuiz, setSavedQuiz] = useState<Quiz | null>(null);
  const [savedQuizConfig, setSavedQuizConfig] = useState<string | null>(null);
  const [questionEdits, setQuestionEdits] = useState<
    Record<string, { co_id: string; marks: string }>
  >({});

  const currentQuizConfig = () =>
    JSON.stringify({
      title: quizTitle.trim(),
      module: quizModule,
      questions: sel,
      opensAt,
      closesAt,
    });

  const { data: subjectList } = useQuery({
    queryKey: ["subjects"],
    queryFn: () => subjects.list(),
  });

  const activeSubject = subjectId ?? subjectList?.[0]?.id ?? null;

  const { data: detail } = useQuery({
    queryKey: ["subject-detail", activeSubject],
    queryFn: () => subjects.get(activeSubject!),
    enabled: !!activeSubject,
  });

  const availableModules = detail?.modules ?? [];
  const allCOs = detail?.cos ?? [];

  const { data: questionBank } = useQuery<Question[]>({
    queryKey: ["question-bank", activeSubject],
    queryFn: async () => {
      if (!availableModules.length) return [];
      const results = await Promise.all(
        availableModules.map((m) =>
          questions.list({ module_id: m.id, status: "approved" }).catch(() => []),
        ),
      );
      return results.flat();
    },
    enabled: !!activeSubject && availableModules.length > 0,
  });

  const { data: existingQuizzes } = useQuery<Quiz[]>({
    queryKey: ["quizzes", activeSubject],
    queryFn: () => quizzes.list({ subject_id: activeSubject! }),
    enabled: !!activeSubject,
  });

  // Validates that closing time is after opening time.
  const validateTimes = (): string | null => {
    if (!opensAt || !closesAt) return null;
    const o = new Date(opensAt);
    const c = new Date(closesAt);
    if (c <= o) return "Closing time must be after opening time.";
    return null;
  };

  const updateQuestionMappingMutation = useMutation({
    mutationFn: async (questionId: string) => {
      const question = questionBank?.find((item) => item.id === questionId);
      const edit = questionEdits[questionId];
      if (!question || !edit) throw new Error("Question changes are no longer available.");
      const marks = Number(edit.marks);
      if (!Number.isFinite(marks) || marks <= 0) {
        throw new Error("Marks must be a number greater than zero.");
      }
      if (!allCOs.some((co) => co.id === edit.co_id)) {
        throw new Error("Select a Course Outcome belonging to this subject.");
      }
      return questions.update(questionId, { co_id: edit.co_id, marks });
    },
    onSuccess: async (_question, questionId) => {
      setQuestionEdits((current) => {
        const next = { ...current };
        delete next[questionId];
        return next;
      });
      await queryClient.invalidateQueries({ queryKey: ["question-bank", activeSubject] });
      toast.success("Question mapping and marks updated.");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Could not update question mapping.");
    },
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const moduleId = quizModule;
      if (!moduleId) throw new Error("Select a module first.");
      if (!quizTitle.trim()) throw new Error("Enter a quiz title.");
      if (picked.length !== sel.length) {
        throw new Error("Some selected questions are no longer available. Refresh the question bank and try again.");
      }
      const questionError = validateQuizQuestionSet(
        picked,
        moduleId,
        allCOs.map((co) => co.id),
      );
      if (questionError) throw new Error(questionError);
      return quizzes.create({
        module_id: moduleId,
        title: quizTitle,
        question_ids: sel,
        opens_at: opensAt ? new Date(opensAt).toISOString() : undefined,
        closes_at: closesAt ? new Date(closesAt).toISOString() : undefined,
      });
    },
    onSuccess: (quiz) => {
      queryClient.invalidateQueries({ queryKey: ["quizzes", activeSubject] });
      setSavedQuiz(quiz);
      setSavedQuizConfig(currentQuizConfig());
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Failed to save quiz.");
    },
  });

  const publishMutation = useMutation({
    mutationFn: async () => {
      const timeErr = validateTimes();
      if (timeErr) throw new Error(timeErr);
      const quiz =
        savedQuiz && savedQuizConfig === currentQuizConfig()
          ? savedQuiz
          : await createMutation.mutateAsync();
      await quizzes.publish(quiz.id);
      return quiz;
    },
    onSuccess: (quiz) => {
      queryClient.invalidateQueries({ queryKey: ["quizzes", activeSubject] });
      setSavedQuiz(null);
      setSavedQuizConfig(null);
      toast.success(`Quiz "${quiz.title}" published`);
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Failed to publish quiz.");
    },
  });

  const handlePublish = () => {
    const timeErr = validateTimes();
    if (timeErr) {
      toast.error(timeErr);
      return;
    }
    if (!quizTitle.trim()) {
      toast.error("Enter a quiz title.");
      return;
    }
    if (!quizModule) {
      toast.error("Select a module.");
      return;
    }
    if (sel.length === 0) {
      toast.error("Add at least one question to the quiz.");
      return;
    }
    if (Object.keys(questionEdits).length > 0) {
      toast.error("Save or discard your pending CO mapping and marks changes before publishing.");
      return;
    }
    publishMutation.mutate();
  };

  const handleSaveDraft = () => {
    if (!quizTitle.trim() || !quizModule) {
      toast.error("Enter a title and select a module.");
      return;
    }
    if (sel.length === 0) {
      toast.error("Add at least one question to the quiz.");
      return;
    }
    if (Object.keys(questionEdits).length > 0) {
      toast.error("Save or discard your pending CO mapping and marks changes before saving the quiz.");
      return;
    }
    createMutation.mutate();
  };

  // A quiz is module-scoped: never mix approved questions from other modules.
  const moduleQuestionBank = filterQuestionsForModule(questionBank ?? [], quizModule);
  const picked = sel
    .map((id) => moduleQuestionBank.find((b) => b.id === id))
    .filter((q): q is Question => q !== undefined);

  const perCO = allCOs.map((co) =>
    picked.filter((question) => (questionEdits[question.id]?.co_id ?? question.co_id) === co.id).length,
  );

  const filteredBank = moduleQuestionBank.filter((b) => {
    const matchesSearch = b.stem.toLowerCase().includes(term.toLowerCase());
    const matchesCO = activeCO === null || b.co_number === activeCO;
    return matchesSearch && matchesCO;
  });

  if (!subjectList?.length) {
    return (
      <Shell role="faculty">
        <PageHead eyebrow="Faculty" title="Quiz Builder" sub="No subjects assigned." />
      </Shell>
    );
  }

  return (
    <Shell role="faculty" subjectLabel={detail ? `${detail.code} · ${detail.name}` : undefined}>
      <Toaster />
      <PageHead
        eyebrow="Teaching · Planner"
        title="Compose a quiz"
        right={
          <div className="flex items-center gap-2">
            {savedQuiz && (
              <span className="font-mono text-xs text-success">
                Draft saved (ID: {savedQuiz.id.substring(0, 8)}...)
              </span>
            )}
            <Btn
              variant="secondary"
              onClick={handleSaveDraft}
              disabled={createMutation.isPending || sel.length === 0}
              size="sm"
            >
              Save as draft
            </Btn>
            <Btn
              size="lg"
              onClick={handlePublish}
              disabled={publishMutation.isPending || sel.length === 0}
            >
              <Send className="size-4" />
              {publishMutation.isPending ? "Publishing…" : "Publish quiz"}
            </Btn>
          </div>
        }
      />
      <div className="grid grid-cols-12 gap-5">
        <Card className="col-span-12">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Field label="Quiz title">
              <input
                className={inputCls}
                value={quizTitle}
                onChange={(e) => setQuizTitle(e.target.value)}
              />
            </Field>
            <Field label="Module">
              <select
                className={inputCls}
                value={quizModule}
                onChange={(e) => {
                  setQuizModule(e.target.value);
                  setSel([]);
                  setQuestionEdits({});
                  setSavedQuiz(null);
                  setSavedQuizConfig(null);
                }}
              >
                <option value="">Select a module</option>
                {availableModules.map((m) => (
                  <option key={m.id} value={m.id}>
                    M{m.number} — {m.title}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Opens">
              <input
                type="datetime-local"
                className={inputCls}
                value={opensAt}
                onChange={(e) => setOpensAt(e.target.value)}
              />
            </Field>
            <Field label="Closes">
              <input
                type="datetime-local"
                className={inputCls}
                value={closesAt}
                onChange={(e) => setClosesAt(e.target.value)}
              />
            </Field>
          </div>
          {quizModule && allCOs.length === 0 && (
            <p role="alert" className="mt-3 rounded-xl border border-warn/30 bg-warn/5 p-3 text-sm text-wine">
              This subject has no approved Course Outcomes. Add and approve its Course Outcomes before mapping and publishing a CO-aware quiz.
            </p>
          )}
          {quizModule && (
            <p className="mt-3 text-xs text-muted-foreground">
              Questions are restricted to the selected module. Before publishing, review each question's CO mapping and marks in the selected list.
            </p>
          )}
        </Card>

        <Card
          className="col-span-12 lg:col-span-6"
          title="Question bank"
          action={
            <span className="font-mono text-[11px] text-muted-foreground">approved only</span>
          }
        >
          <div className="relative mb-3">
            <Search className="absolute left-4 top-3.5 size-4 text-muted-foreground" />
            <input
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="Search questions"
              className={`${inputCls} pl-10`}
            />
          </div>
          <div className="mb-3 flex flex-wrap gap-1.5">
            {allCOs.map((co) => (
              <button
                key={co.number}
                type="button"
                onClick={() => setActiveCO(activeCO === co.number ? null : co.number)}
                className={cn(
                  "cursor-pointer rounded-full p-0.5",
                  activeCO === co.number && "ring-2 ring-wine",
                )}
              >
                <CO n={co.number} />
              </button>
            ))}
          </div>
          {filteredBank.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {!quizModule
                ? "Select a module to see its approved questions."
                : moduleQuestionBank.length === 0
                  ? "No approved questions for this module yet. Upload its PPTX, then review and approve generated questions."
                  : "No questions match your filters."}
            </p>
          ) : (
            filteredBank.map((b) => (
              <div
                key={b.id}
                className="flex items-center gap-3 border-b border-dashed border-wine/20 py-3 last:border-0"
              >
                <CO n={b.co_number} />
                <span className="flex-1 text-sm">{b.stem}</span>
                <Btn
                  size="sm"
                  variant={sel.includes(b.id) ? "ghost" : "secondary"}
                  disabled={sel.includes(b.id)}
                  onClick={() =>
                    sel.includes(b.id)
                      ? setSel(sel.filter((x) => x !== b.id))
                      : setSel([...sel, b.id])
                  }
                >
                  <Plus className="size-3.5" />
                  {sel.includes(b.id) ? "Added" : "Add"}
                </Btn>
              </div>
            ))
          )}
        </Card>

        <div className="col-span-6 space-y-5">
          <div className="paper-wine p-5">
            <div className="flex items-end justify-between">
              <div>
                <div className="eyebrow !text-beige/70">Total questions</div>
                <div className="display text-5xl text-ivory">{picked.length}</div>
              </div>
              <div className="flex gap-3">
                {perCO.map((c, i) => (
                  <div key={i} className="text-center">
                    <div className="font-mono text-lg">{c}</div>
                    <div className="font-mono text-[10px] text-beige/70">CO{i + 1}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <Card
            title={`Selected · ${picked.length}`}
            action={
              <span className="font-mono text-xs text-muted-foreground">
                {picked.reduce(
                  (sum, question) =>
                    sum + Number(questionEdits[question.id]?.marks ?? question.marks ?? 1),
                  0,
                )} marks
              </span>
            }
          >
            {picked.length === 0 && (
              <p className="py-8 text-center font-serif text-lg text-muted-foreground">
                Nothing pinned yet — add from the bank.
              </p>
            )}
            {picked.map((p, i) => (
              <div
                key={p.id}
                draggable
                onDragStart={() => setDrag(i)}
                onDragOver={(e) => {
                  e.preventDefault();
                  if (drag !== null && drag !== i) {
                    const n = [...sel];
                    const [x] = n.splice(drag, 1);
                    n.splice(i, 0, x!);
                    setSel(n);
                    setDrag(i);
                  }
                }}
                onDragEnd={() => setDrag(null)}
                className={cn(
                  "mb-2 flex flex-wrap cursor-grab items-center gap-3 rounded-xl border border-wine/15 bg-beige/40 px-3 py-2.5",
                  drag === i && "opacity-50",
                )}
              >
                <GripVertical className="size-4 text-wine/50" />
                <span className="font-mono text-xs text-wine">{i + 1}.</span>
                <span className="min-w-0 flex-1 text-sm">{p.stem}</span>
                <div className="flex flex-wrap items-center gap-2">
                  <label className="sr-only" htmlFor={`co-map-${p.id}`}>Course Outcome for question {i + 1}</label>
                  <select
                    id={`co-map-${p.id}`}
                    className="h-9 max-w-36 rounded-lg border border-wine/20 bg-background px-2 text-xs"
                    value={questionEdits[p.id]?.co_id ?? p.co_id ?? ""}
                    disabled={updateQuestionMappingMutation.isPending}
                    onChange={(event) => setQuestionEdits((current) => ({
                      ...current,
                      [p.id]: {
                        co_id: event.target.value,
                        marks: current[p.id]?.marks ?? String(p.marks ?? 1),
                      },
                    }))}
                    aria-label={`Map question ${i + 1} to Course Outcome`}
                  >
                    <option value="" disabled>Select a Course Outcome</option>
                    {allCOs.map((co) => (
                      <option key={co.id} value={co.id}>CO{co.number}</option>
                    ))}
                  </select>
                  <label className="sr-only" htmlFor={`marks-${p.id}`}>Marks for question {i + 1}</label>
                  <input
                    id={`marks-${p.id}`}
                    type="number"
                    min="1"
                    step="1"
                    className="h-9 w-16 rounded-lg border border-wine/20 bg-background px-2 text-xs"
                    value={questionEdits[p.id]?.marks ?? String(p.marks ?? 1)}
                    disabled={updateQuestionMappingMutation.isPending}
                    onChange={(event) => setQuestionEdits((current) => ({
                      ...current,
                      [p.id]: {
                        co_id: current[p.id]?.co_id ?? p.co_id ?? "",
                        marks: event.target.value,
                      },
                    }))}
                    aria-label={`Marks for question ${i + 1}`}
                  />
                  {questionEdits[p.id] && (
                    <>
                      <Btn
                        size="sm"
                        variant="ghost"
                        disabled={updateQuestionMappingMutation.isPending}
                        onClick={() => setQuestionEdits((current) => {
                          const next = { ...current };
                          delete next[p.id];
                          return next;
                        })}
                      >
                        Cancel
                      </Btn>
                      <Btn
                        size="sm"
                        variant="secondary"
                        disabled={updateQuestionMappingMutation.isPending}
                        onClick={() => updateQuestionMappingMutation.mutate(p.id)}
                      >
                        <Save className="size-3.5" /> Save
                      </Btn>
                    </>
                  )}
                </div>
                <button onClick={() => setSel(sel.filter((x) => x !== p.id))} aria-label="Remove question">

                  <X className="size-4 text-wine" />
                </button>
              </div>
            ))}
          </Card>
        </div>

        <Card className="col-span-12" title="Existing quizzes">
          {!existingQuizzes?.length ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No quizzes created yet.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {existingQuizzes.map((q) => (
                <div key={q.id} className="rounded-xl border border-wine/15 p-4">
                  <Chip s={q.published ? "Published" : "Draft"} />
                  <div className="mt-2 font-serif text-lg text-wine">{q.title}</div>
                  <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                    opens{" "}
                    {q.opens_at
                      ? new Date(q.opens_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })
                      : "—"}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </Shell>
  );
}
