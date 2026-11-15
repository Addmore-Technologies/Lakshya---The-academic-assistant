import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Check, Pencil, Sparkle, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { Shell } from "@/components/lk/Shell";
import { Btn, Card, Chip, CO, Field, inputCls, PageHead, type Status } from "@/components/lk/ui";
import { cn } from "@/lib/utils";
import { agent, ApiError, questions, subjects } from "@/lib/api";
import { getStoredSubjectId, storeSubjectId } from "@/lib/subject-context";
import type { Question, SubjectDetail } from "@/lib/api";

export const Route = createFileRoute("/faculty/review")({
  head: () => ({
    meta: [
      { title: "Question Review · LAKSHYA" },
      { name: "description", content: "Moderate AI-generated and faculty questions." },
      { property: "og:title", content: "Question Review · LAKSHYA" },
      {
        property: "og:description",
        content: "Approve, edit or reject questions before they reach students.",
      },
    ],
  }),
  component: Page,
});

function Page() {
  const queryClient = useQueryClient();
  const [subjectId, setSubjectId] = useState<string | null>(() => getStoredSubjectId());
  const [filter, setFilter] = useState<Status | "All">("All");
  const [sourceFilter, setSourceFilter] = useState<"All" | "AI" | "Faculty">("All");
  const [coFilter, setCoFilter] = useState<number | null>(null);
  const [genModule, setGenModule] = useState<string>("");
  const [genCO, setGenCO] = useState<string>("");
  const [genCount, setGenCount] = useState("5");
  const [genDifficulty, setGenDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [moduleFilter, setModuleFilter] = useState<string>("All");
  const [difficultyFilter, setDifficultyFilter] = useState<string>("All");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editStem, setEditStem] = useState("");
  const [editOptions, setEditOptions] = useState<string[]>([]);
  const [editCorrect, setEditCorrect] = useState(0);
  const [editExplanation, setEditExplanation] = useState("");
  const [editMarks, setEditMarks] = useState("1");
  const [editCOId, setEditCOId] = useState("");

  const { data: subjectList } = useQuery({
    queryKey: ["subjects"],
    queryFn: () => subjects.list(),
  });

  const activeSubject = subjectId ?? subjectList?.[0]?.id ?? null;

  const { data: detail } = useQuery<SubjectDetail>({
    queryKey: ["subject-detail", activeSubject],
    queryFn: () => subjects.get(activeSubject!),
    enabled: !!activeSubject,
  });

  const availableModules = detail?.modules ?? [];
  const allCOs = detail?.cos ?? [];

  const {
    data: allQuestions,
    isLoading: questionsLoading,
    isError: questionsError,
    refetch: refetchQuestions,
  } = useQuery<Question[]>({
    queryKey: ["review-questions", activeSubject],
    queryFn: async () => {
      if (!availableModules.length) return [];
      const results = await Promise.all(
        availableModules.map((m) => questions.list({ module_id: m.id }).catch(() => [])),
      );
      return results.flat();
    },
    enabled: !!activeSubject && availableModules.length > 0,
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      const count = Number(genCount);
      if (!genModule || !genCO) throw new Error("Select a module and Course Outcome.");
      if (!Number.isInteger(count) || count < 1 || count > 20) {
        throw new Error("Choose between 1 and 20 questions.");
      }
      const module = availableModules.find((item) => item.id === genModule);
      const co = allCOs.find((item) => item.id === genCO);
      if (!module || !co) throw new Error("The selected module or Course Outcome is no longer available.");
      const message = [
        "Use the generate_quiz tool exactly once with these exact arguments.",
        `module_id: ${genModule}`,
        `co_id: ${genCO}`,
        `difficulty: ${genDifficulty}`,
        `count: ${count}`,
        "Do not ask follow-up questions. Do not invent IDs. After the tool completes, briefly report the result.",
      ].join("\n");
      const result = await agent.chat(message);
      const generated = result.tool_calls.some(
        (call) => call.name === "generate_quiz" && call.status === "draft_review",
      );
      if (!generated) {
        throw new Error(result.reply || "The AI agent did not generate question drafts. Check that AI services are configured.");
      }
      return result;
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["review-questions", activeSubject] });
      toast.success("AI question drafts generated. Review and approve them before adding them to a quiz.");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Could not generate AI question drafts.");
    },
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => questions.approve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["review-questions", activeSubject],
      });
      toast.success("Question approved");
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Approval failed.");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => questions.reject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["review-questions", activeSubject],
      });
      toast.success("Question rejected");
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Rejection failed.");
    },
  });

  const updateMutation = useMutation({
    mutationFn: (id: string) =>
      questions.update(id, {
        stem: editStem.trim(),
        options: editOptions.map((option) => option.trim()),
        correct_option: editCorrect,
        explanation: editExplanation.trim(),
        marks: Number(editMarks),
        co_id: editCOId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-questions", activeSubject] });
      setEditingId(null);
      toast.success("Question updated");
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Could not save question changes.");
    },
  });

  const startEditing = (q: Question) => {
    setEditingId(q.id);
    setEditStem(q.stem);
    setEditOptions([...q.options]);
    setEditCorrect(q.correct_option);
    setEditExplanation(q.explanation ?? "");
    setEditMarks(String(q.marks ?? 1));
    setEditCOId(q.co_id);
  };

  const set = (id: string, s: Status) => {
    if (s === "Approved") approveMutation.mutate(id);
    else if (s === "Rejected") rejectMutation.mutate(id);
  };

  const displayStatus = (status: string): Status =>
    (status.charAt(0).toUpperCase() + status.slice(1).toLowerCase()) as Status;

  const visible = (allQuestions ?? []).filter((q) => {
    const matchesStatus = filter === "All" || displayStatus(q.status) === filter;
    const normalizedSource = q.source.toLowerCase();
    const matchesSource =
      sourceFilter === "All" ||
      (sourceFilter === "AI" && normalizedSource === "ai") ||
      (sourceFilter === "Faculty" && normalizedSource === "faculty");
    const matchesCO = coFilter === null || q.co_number === coFilter;
    const matchesModule = moduleFilter === "All" || q.module_id === moduleFilter;
    const matchesDifficulty =
      difficultyFilter === "All" ||
      (q.difficulty ?? "").toLowerCase() === difficultyFilter.toLowerCase();
    return matchesStatus && matchesSource && matchesCO && matchesModule && matchesDifficulty;
  });

  const count = (s: Status) =>
    (allQuestions ?? []).filter((q) => displayStatus(q.status) === s).length;

  if (!subjectList?.length) {
    return (
      <Shell role="faculty" subjectLabel={detail ? `${detail.code} · ${detail.name}` : undefined}>
        <PageHead eyebrow="Faculty" title="Question Review" sub="No subjects assigned." />
      </Shell>
    );
  }

  return (
    <Shell role="faculty" subjectLabel={detail ? `${detail.code} · ${detail.name}` : undefined}>
      <Toaster />
      <PageHead
        eyebrow="Teaching · Moderation"
        title="Question review"
        right={
          <Btn
            disabled={
              approveMutation.isPending || !visible.some((q) => displayStatus(q.status) === "Draft")
            }
            onClick={async () => {
              const draftIds = visible
                .filter((q) => displayStatus(q.status) === "Draft")
                .map((q) => q.id);
              try {
                await Promise.all(draftIds.map((id) => questions.approve(id)));
                await queryClient.invalidateQueries({
                  queryKey: ["review-questions", activeSubject],
                });
                toast.success(`Approved ${draftIds.length} questions`);
              } catch (error) {
                if (error instanceof ApiError) toast.error(error.message);
                else toast.error("Some questions could not be approved. Refresh and retry.");
                queryClient.invalidateQueries({ queryKey: ["review-questions", activeSubject] });
              }
            }}
          >
            <Check className="size-4" />
            Approve all visible
          </Btn>
        }
      />
      <Card className="mb-5" title="Generate AI question drafts">
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Generate draft questions from processed slide content tagged to one approved Course Outcome. Generated questions are never published automatically; review, edit and approve them below.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Field label="Module">
              <select className={inputCls} value={genModule} onChange={(e) => setGenModule(e.target.value)}>
                <option value="">Select module</option>
                {availableModules.map((module) => (
                  <option key={module.id} value={module.id}>M{module.number} · {module.title}</option>
                ))}
              </select>
            </Field>
            <Field label="Course Outcome">
              <select className={inputCls} value={genCO} onChange={(e) => setGenCO(e.target.value)}>
                <option value="">Select approved CO</option>
                {allCOs.map((co) => (
                  <option key={co.id} value={co.id}>CO{co.number} · {co.description}</option>
                ))}
              </select>
            </Field>
            <Field label="Difficulty">
              <select className={inputCls} value={genDifficulty} onChange={(e) => setGenDifficulty(e.target.value as "easy" | "medium" | "hard")}>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </Field>
            <Field label="Number of questions (1–20)">
              <input className={inputCls} type="number" min="1" max="20" step="1" value={genCount} onChange={(e) => setGenCount(e.target.value)} />
            </Field>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              Requires a processed PPTX with slides tagged to the selected CO. If no tagged slides exist, the backend will explain why generation cannot proceed.
            </p>
            <Btn
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending || !genModule || !genCO || !allCOs.length}
            >
              <Sparkle className="size-4" />
              {generateMutation.isPending ? "Generating drafts…" : "Generate question drafts"}
            </Btn>
          </div>
        </div>
      </Card>
      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-12 lg:col-span-8 space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2">
            {(["All", "Draft", "Approved", "Rejected"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={cn(
                  "rounded-full border px-4 py-1.5 text-sm",
                  filter === s ? "border-wine bg-wine text-ivory" : "border-wine/30 text-wine",
                )}
              >
                {s}{" "}
                {s !== "All" && (
                  <span className="ml-1 font-mono text-[11px] opacity-70">
                    {count(s as Status)}
                  </span>
                )}
              </button>
            ))}
            <div className="flex-1" />
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value as "All" | "AI" | "Faculty")}
              className="h-9 rounded-full border border-wine/30 bg-ivory px-3 text-xs text-wine"
            >
              <option value="All">Source: All</option>
              <option value="AI">AI</option>
              <option value="Faculty">Faculty</option>
            </select>
            <select
              value={coFilter ?? ""}
              onChange={(e) => setCoFilter(e.target.value ? Number(e.target.value) : null)}
              className="h-9 rounded-full border border-wine/30 bg-ivory px-3 text-xs text-wine"
            >
              <option value="">CO: All</option>
              {allCOs.map((co) => (
                <option key={co.id} value={co.number}>
                  CO{co.number}
                </option>
              ))}
            </select>
            <select
              value={moduleFilter}
              onChange={(e) => setModuleFilter(e.target.value)}
              className="h-9 rounded-full border border-wine/30 bg-ivory px-3 text-xs text-wine"
              aria-label="Filter by module"
            >
              <option value="All">Module: All</option>
              {availableModules.map((module) => (
                <option key={module.id} value={module.id}>
                  M{module.number} · {module.title}
                </option>
              ))}
            </select>
            <select
              className="h-9 rounded-full border border-wine/30 bg-ivory px-3 text-xs text-wine"
              value={difficultyFilter}
              onChange={(e) => setDifficultyFilter(e.target.value)}
              aria-label="Filter by difficulty"
            >
              <option value="All">Difficulty: All</option>
              {[
                ...new Set(
                  (allQuestions ?? [])
                    .map((question) => question.difficulty)
                    .filter((value): value is string => Boolean(value)),
                ),
              ].map((difficulty) => (
                <option key={difficulty} value={difficulty}>
                  {difficulty}
                </option>
              ))}
            </select>
          </div>

          {/* Question list */}
          {questionsLoading ? (
            <p role="status" className="py-8 text-center text-sm text-muted-foreground">
              Loading questions…
            </p>
          ) : questionsError ? (
            <div role="alert" className="rounded-xl bg-wine/10 p-5 text-center text-sm text-wine">
              <p>Questions could not be loaded.</p>
              <Btn
                size="sm"
                variant="secondary"
                className="mt-3"
                onClick={() => refetchQuestions()}
              >
                Retry
              </Btn>
            </div>
          ) : visible.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No questions match your filters.
            </p>
          ) : (
            visible.map((q) => {
              const mod = availableModules.find((m) => m.id === q.module_id);
              return (
                <article key={q.id} className="paper p-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[11px] text-muted-foreground">
                      Q{q.id.substring(0, 8)} · M{mod?.number ?? "?"}
                    </span>
                    <CO n={q.co_number} />
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[11px]",
                        q.source.toLowerCase() === "ai"
                          ? "bg-dusty text-oxblood"
                          : "bg-beige text-wine",
                      )}
                    >
                      {q.source.toLowerCase() === "ai" ? "✦ AI" : "Faculty"}
                    </span>
                    {q.difficulty && (
                      <span className="text-[11px] text-muted-foreground">{q.difficulty}</span>
                    )}
                    {q.bloom_level && (
                      <span className="text-[11px] text-muted-foreground">Bloom: {q.bloom_level}</span>
                    )}
                    <span className="text-[11px] text-muted-foreground">{q.marks ?? 1} mark(s)</span>
                    <div className="flex-1" />
                    <Chip s={displayStatus(q.status)} />
                  </div>
                  <p className="mt-3 font-serif text-xl font-semibold text-espresso">{q.stem}</p>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {q.options.map((o, i) => (
                      <div
                        key={i}
                        className={cn(
                          "flex items-center gap-2 rounded-xl border px-3 py-2 text-sm",
                          i === q.correct_option
                            ? "border-success bg-success/10"
                            : "border-wine/15",
                        )}
                      >
                        <span className="font-mono text-xs text-muted-foreground">{"ABCD"[i]}</span>
                        {o}
                        {i === q.correct_option && (
                          <Check className="ml-auto size-4 text-success" />
                        )}
                      </div>
                    ))}
                  </div>
                  {editingId === q.id && (
                    <div className="mt-4 space-y-3 rounded-xl border border-wine/20 bg-beige/30 p-4">
                      <Field label="Question text">
                        <textarea
                          className={inputCls}
                          rows={3}
                          value={editStem}
                          onChange={(e) => setEditStem(e.target.value)}
                        />
                      </Field>
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        {editOptions.map((option, index) => (
                          <Field key={index} label={`Option ${"ABCD"[index]}`}>
                            <input
                              className={inputCls}
                              value={option}
                              onChange={(e) =>
                                setEditOptions((current) =>
                                  current.map((value, i) => (i === index ? e.target.value : value)),
                                )
                              }
                            />
                          </Field>
                        ))}
                      </div>
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <Field label="Course Outcome mapping">
                          <select
                            className={inputCls}
                            value={editCOId}
                            onChange={(e) => setEditCOId(e.target.value)}
                          >
                            {allCOs.map((co) => (
                              <option key={co.id} value={co.id}>CO{co.number} · {co.description}</option>
                            ))}
                          </select>
                        </Field>
                        <Field label="Marks">
                          <input
                            type="number"
                            min="1"
                            step="1"
                            className={inputCls}
                            value={editMarks}
                            onChange={(e) => setEditMarks(e.target.value)}
                          />
                        </Field>
                      </div>
                      <Field label="Correct option">
                        <select
                          className={inputCls}
                          value={editCorrect}
                          onChange={(e) => setEditCorrect(Number(e.target.value))}
                        >
                          {editOptions.map((_, index) => (
                            <option key={index} value={index}>
                              Option {"ABCD"[index]}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Explanation">
                        <textarea
                          className={inputCls}
                          rows={2}
                          value={editExplanation}
                          onChange={(e) => setEditExplanation(e.target.value)}
                        />
                      </Field>
                      <div className="flex justify-end gap-2">
                        <Btn variant="ghost" size="sm" onClick={() => setEditingId(null)}>
                          Cancel
                        </Btn>
                        <Btn
                          size="sm"
                          disabled={
                            updateMutation.isPending ||
                            !editStem.trim() ||
                            !editCOId ||
                            !Number.isFinite(Number(editMarks)) ||
                            Number(editMarks) <= 0 ||
                            editOptions.length < 2 ||
                            editOptions.some((option) => !option.trim())
                          }
                          onClick={() => updateMutation.mutate(q.id)}
                        >
                          {updateMutation.isPending ? "Saving…" : "Save changes"}
                        </Btn>
                      </div>
                    </div>
                  )}
                  {q.explanation && (
                    <p className="mt-3 border-l-2 border-dusty pl-3 text-sm text-muted-foreground">
                      <b className="text-espresso">Why:</b> {q.explanation}
                    </p>
                  )}
                  <div className="mt-4 flex justify-end gap-2">
                    <Btn
                      variant="ghost"
                      size="sm"
                      onClick={() => (editingId === q.id ? setEditingId(null) : startEditing(q))}
                    >
                      <Pencil className="size-3.5" />
                      {editingId === q.id ? "Close editor" : "Edit"}
                    </Btn>
                    <Btn
                      variant="secondary"
                      size="sm"
                      onClick={() => set(q.id, "Rejected")}
                      disabled={displayStatus(q.status) === "Rejected"}
                    >
                      <X className="size-3.5" />
                      Reject
                    </Btn>
                    <Btn
                      size="sm"
                      onClick={() => set(q.id, "Approved")}
                      disabled={displayStatus(q.status) === "Approved"}
                    >
                      <Check className="size-3.5" />
                      Approve
                    </Btn>
                  </div>
                </article>
              );
            })
          )}
        </div>

        {/* Sidebar */}
        <div className="col-span-12 lg:col-span-4">
          <div className="sticky top-24 space-y-5">
            <div className="grid grid-cols-3 gap-3">
              {(["Draft", "Approved", "Rejected"] as const).map((s) => (
                <div key={s} className="paper p-4 text-center">
                  <div className="display text-4xl text-wine">{count(s)}</div>
                  <div className="eyebrow">{s}</div>
                </div>
              ))}
            </div>

          </div>
        </div>
      </div>
    </Shell>
  );
}
