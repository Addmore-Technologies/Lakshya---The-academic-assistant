import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Download } from "lucide-react";
import { Fragment, useState } from "react";
import { Shell } from "@/components/lk/Shell";
import { Bar, Btn, Card, CO, PageHead } from "@/components/lk/ui";
import { cn } from "@/lib/utils";
import { ApiError, coSheet, subjects } from "@/lib/api";
import { getStoredSubjectId, storeSubjectId } from "@/lib/subject-context";
import { averageAssessedPercentages } from "@/lib/analytics-display";
import type { COSheet, COSummaryItem, WeakCO } from "@/lib/api";

export const Route = createFileRoute("/faculty/analytics")({
  head: () => ({
    meta: [
      { title: "CO Sheet & Analytics · LAKSHYA" },
      {
        name: "description",
        content: "Course outcome attainment per student, with charts and exports.",
      },
      { property: "og:title", content: "CO Sheet & Analytics · LAKSHYA" },
      { property: "og:description", content: "Professional CO attainment reporting." },
    ],
  }),
  component: Page,
});

function Page() {
  const [subjectId, setSubjectId] = useState<string | null>(() => getStoredSubjectId());
  const [scope, setScope] = useState<"semester" | "module">("semester");
  const [moduleId, setModuleId] = useState<string | null>(null);
  const [section, setSection] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [expandedStudent, setExpandedStudent] = useState<string | null>(null);

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

  const { data: sectionSource } = useQuery<COSheet>({
    queryKey: ["co-sheet-sections", activeSubject, scope, moduleId],
    queryFn: () => coSheet.getSheet(activeSubject!, { scope, module_id: moduleId ?? undefined }),
    enabled: !!activeSubject && (scope !== "module" || !!moduleId),
  });

  const { data: sheets } = useQuery<COSheet>({
    queryKey: ["co-sheet", activeSubject, scope, moduleId, section],
    queryFn: () =>
      coSheet.getSheet(activeSubject!, {
        scope,
        module_id: moduleId ?? undefined,
        section: section || undefined,
      }),
    enabled: !!activeSubject && (scope !== "module" || !!moduleId),
  });

  const { data: coSummary } = useQuery<COSummaryItem[]>({
    queryKey: ["co-summary", activeSubject, section],
    queryFn: () => coSheet.getSummary(activeSubject!, section || undefined),
    enabled: !!activeSubject && scope === "semester",
  });

  const { data: weakCOs } = useQuery<WeakCO[]>({
    queryKey: ["weak-co", activeSubject, section],
    queryFn: () => coSheet.getWeakCOs(activeSubject!, section || undefined),
    enabled: !!activeSubject && scope === "semester",
  });

  // ── Derived values ──────────────────────────────────────────────────
  const cols = sheets?.columns ?? [];
  const sheetRows = sheets?.rows ?? [];

  const AVG = cols.map((col) => {
    const value = sheets?.averages[col];
    return value === null || value === undefined ? null : Math.round(value);
  });

  // Score distribution: [0-40, 40-50, 50-60, 60-70, 70-80, 80+]
  const assessedRows = sheetRows.filter((row) => row.total_max > 0);
  const DIST = [
    assessedRows.filter((r) => r.total_pct < 40).length,
    assessedRows.filter((r) => r.total_pct >= 40 && r.total_pct < 50).length,
    assessedRows.filter((r) => r.total_pct >= 50 && r.total_pct < 60).length,
    assessedRows.filter((r) => r.total_pct >= 60 && r.total_pct < 70).length,
    assessedRows.filter((r) => r.total_pct >= 70 && r.total_pct < 80).length,
    assessedRows.filter((r) => r.total_pct >= 80).length,
  ];
  const targetPct = detail?.target_attainment_pct ?? 60;
  const thresholdForColumn = (column: string) => {
    const number = Number(column.replace(/^CO/i, ""));
    return detail?.cos?.find((item) => item.number === number)?.threshold_pct
      ?? coSummary?.find((item) => item.co_number === number)?.threshold_pct
      ?? targetPct;
  };
  const avgOverall = averageAssessedPercentages(AVG);
  const availableSections = Array.from(new Set((sectionSource?.rows ?? []).map((row) => row.section).filter(Boolean))).sort();

  const weakInsights = (weakCOs ?? []).filter((w) => w.attainment_pct !== null).slice(0, 2).map((w) => {
    const co = detail?.cos?.find((c) => c.number === w.co_number);
    const summary = coSummary?.find((s) => s.co_number === w.co_number);
    return {
      co: w.co_number,
      pct: w.attainment_pct as number,
      desc: co?.description ?? `CO${w.co_number}`,
      insight: summary
        ? `${summary.below} of ${summary.enrolled} students below ${summary.threshold_pct}% threshold`
        : `${Math.round(w.gap ?? 0)}% below target`,
    };
  });

  const handleExport = async () => {
    if (!activeSubject) return;
    setExporting(true);
    setError(null);
    try {
      const { blob, filename } = await coSheet.exportSheet(activeSubject, {
        scope,
        module_id: moduleId ?? undefined,
        section: section || undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safeCode = (detail?.code ?? "subject").replace(/[^a-zA-Z0-9_-]/g, "") || "subject";
      a.download = filename ?? `co_sheet_${safeCode}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else setError("Export failed.");
    } finally {
      setExporting(false);
    }
  };

  if (!subjectList?.length) {
    return (
      <Shell role="faculty">
        <PageHead eyebrow="Faculty" title="Analytics" sub="No subjects assigned." />
      </Shell>
    );
  }

  return (
    <Shell role="faculty" subjectLabel={detail ? `${detail.code} · ${detail.name}` : undefined}>
      <PageHead
        eyebrow="Reports · Attainment"
        title="CO sheet"
        right={
          <div className="flex items-center gap-3">
            {subjectList.length > 1 && (
              <select
                value={activeSubject ?? ""}
                onChange={(e) => {
                  const val = e.target.value || null;
                  setSubjectId(val);
                  if (val) storeSubjectId(val);
                  setModuleId(null);
                  setSection("");
                }}
                className="h-10 rounded-full border border-wine/30 bg-ivory px-4 text-sm text-wine"
              >
                {subjectList.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
              </select>
            )}
            <div className="flex rounded-full bg-ivory p-1">
              {(
                [
                  ["Semester", "semester"],
                  ["Module", "module"],
                ] as const
              ).map(([label, val]) => (
                <button
                  key={val}
                  onClick={() => {
                    setScope(val);
                    setModuleId(null);
                    setSection("");
                  }}
                  className={cn(
                    "rounded-full px-4 py-1.5 text-sm",
                    scope === val ? "bg-wine text-ivory" : "text-wine hover:bg-beige/50",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            {scope === "module" && (
              <select
                value={moduleId ?? ""}
                onChange={(e) => { setModuleId(e.target.value || null); setSection(""); }}
                className="h-10 rounded-full border border-wine/30 bg-ivory px-4 text-sm text-wine"
              >
                <option value="">Select module</option>
                {detail?.modules?.map((m) => (
                  <option key={m.id} value={m.id}>
                    M{m.number} — {m.title}
                  </option>
                ))}
              </select>
            )}
            <select
              value={section}
              onChange={(e) => setSection(e.target.value)}
              className="h-10 rounded-full border border-wine/30 bg-ivory px-4 text-sm text-wine"
            >
              <option value="">All sections</option>
              {availableSections.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <Btn variant="secondary" onClick={handleExport} disabled={exporting || (scope === "module" && !moduleId)}>
              <Download className="size-4" />
              {exporting ? "Preparing…" : "Export to Excel"}
            </Btn>
          </div>
        }
      />
      {error && <div role="alert" className="mb-4 rounded-xl border border-wine/20 bg-wine/5 px-4 py-3 text-sm text-wine">{error}</div>}
      <div className="grid grid-cols-12 gap-5">
        <Card className="col-span-7" title="Average score by CO">
          {cols.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No data available for this scope.
            </p>
          ) : (
            <>
              <div className="relative flex h-56 items-end gap-5 border-b border-wine/20 pl-3">
                {AVG.map((v, i) => (
                  <div key={i} className="relative flex flex-1 flex-col items-center justify-end" style={{ height: "100%" }}>
                    <div className="absolute -top-2 rounded-md bg-oxblood px-2 py-1 font-mono text-[11px] text-ivory">
                      {v === null ? "N/A" : `${v}%`}
                    </div>
                    {v !== null && <div className={cn("w-full rounded-t-lg transition", v < targetPct ? "bg-wine" : "bg-dusty")} style={{ height: `${Math.max(v, 1)}%` }} />}
                  </div>
                ))}
              </div>
              <div className="mt-3 flex gap-5 pl-3">
                {AVG.map((_, i) => (
                  <div key={i} className="flex flex-1 justify-center">
                    <CO n={i + 1} />
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="mt-3 flex gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm bg-dusty" />
              Meets target
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm bg-wine" />
              Below target
            </span>
            <span className="text-xs">Each CO uses its configured threshold shown below.</span>
          </div>
        </Card>

        <Card className="col-span-5" title="Score distribution">
          {sheetRows.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No student data for this scope.
            </p>
          ) : (
            <>
              <div className="flex h-56 items-end gap-2">
                {DIST.map((d, i) => (
                  <div key={i} className="flex flex-1 flex-col items-center gap-1">
                    <span className="font-mono text-[10px]">{d}</span>
                    <div
                      className="stripes-blue w-full rounded-t-md border border-dusty"
                      style={{ height: `${d * 10}px` }}
                    />
                  </div>
                ))}
              </div>
              <div className="mt-2 flex gap-2 font-mono text-[10px] text-muted-foreground">
                {["0-40", "40-50", "50-60", "60-70", "70-80", "80+"].map((l) => (
                  <span key={l} className="flex-1 text-center">
                    {l}
                  </span>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card className="col-span-12 !p-0 overflow-hidden">
          <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-wine text-ivory">
              <tr>
                {["USN", "Name", ...cols, "Total", "Status"].map((h, i) => (
                  <th
                    key={h}
                    className={cn("px-4 py-3 font-medium", i < 2 ? "text-left" : "text-right")}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sheetRows.map((r) => (
                <Fragment key={r.usn}>
                <tr className="border-b border-wine/10 even:bg-beige/30">
                  <td className="px-4 py-3 font-mono text-xs">{r.usn}</td>
                  <td className="px-4 py-3">{r.name}</td>
                  {cols.map((col) => {
                    const score = r.co_scores[col];
                    const isNull = score === null || score === undefined;
                    return (
                      <td key={col} className="px-4 py-3 text-right font-mono">
                        <span
                          className={cn(
                            "rounded px-1.5 py-0.5",
                            !isNull && score < thresholdForColumn(col) && "bg-wine/10 font-semibold text-wine",
                          )}
                        >
                          {isNull ? "Not assessed" : `${Math.round(score)}%`}
                        </span>
                      </td>
                    );
                  })}
                  <td className="px-4 py-3 text-right font-mono font-semibold">
                    {r.total_max > 0 ? `${Math.round(r.total_pct)}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-xs">{r.total_max > 0 ? "Assessed" : "Not assessed"}</td>
                </tr>
                <tr className="border-b border-wine/10 bg-beige/20">
                  <td colSpan={2 + cols.length + 2} className="px-4 py-2 text-right">
                    <button className="text-xs font-semibold text-wine underline" onClick={() => setExpandedStudent(expandedStudent === r.usn ? null : r.usn)}>
                      {expandedStudent === r.usn ? "Hide details" : "View CO breakdown"}
                    </button>
                    {expandedStudent === r.usn && <div className="mt-2 flex flex-wrap justify-end gap-3 text-xs">{cols.map((col) => <span key={col}>{col}: {r.co_scores[col] == null ? "Not assessed" : `${Math.round(r.co_scores[col])}%`}</span>)}</div>}
                  </td>
                </tr>
                </Fragment>
              ))}
              <tr className="bg-dusty/40 font-medium">
                <td className="px-4 py-3 eyebrow !text-oxblood" colSpan={2}>
                  Average attainment
                </td>
                {AVG.map((v, i) => (
                  <td
                    key={i}
                    className={cn("px-4 py-3 text-right font-mono", v !== null && v < thresholdForColumn(cols[i] ?? "") && "text-wine")}
                  >
                    {v === null ? "Not assessed" : `${v}%`}
                  </td>
                ))}
                <td className="px-4 py-3 text-right font-mono">{avgOverall === null ? "—" : `${avgOverall}%`}</td>
                <td className="px-4 py-3" />
              </tr>
            </tbody>
          </table>
          </div>
        </Card>

        <Card className="col-span-12" title="CO attainment summary">
          {scope === "module" ? (
            <p className="text-sm text-muted-foreground">The current backend summary endpoint reports semester-level attainment only. Module-level CO scores are shown in the table above.</p>
          ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {(coSummary ?? []).map((item) => {
              const co = detail?.cos?.find((candidate) => candidate.number === item.co_number);
              const assessed = item.average !== null && item.attempted > 0;
              return (
                <div key={item.co_number} className="rounded-xl border border-wine/15 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2"><CO n={item.co_number} /><span className="text-sm font-medium">{co?.description ?? `CO${item.co_number}`}</span></div>
                    <span className="font-mono text-sm">{assessed ? `${Math.round(item.average as number)}%` : "Not assessed"}</span>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{item.attempted} of {item.enrolled} students assessed · threshold {item.threshold_pct}% · target {item.target_pct}%</p>
                  {assessed && <p className={cn("mt-2 text-xs font-semibold", item.met ? "text-success" : "text-wine")}>{item.met ? "Threshold met" : `${item.below} students below threshold`}</p>}
                </div>
              );
            })}
          </div>
          )}
        </Card>

        {scope === "semester" && weakInsights.map((w) => (
          <div key={w.co} className="paper-wine col-span-6 p-6">
            <div className="flex items-center gap-3">
              <CO n={w.co} className="!bg-ivory !text-wine" />
              <span className="font-serif text-2xl">{w.desc}</span>
              <span className="ml-auto font-mono">{w.pct}%</span>
            </div>
            <p className="mt-2 text-sm text-beige/90">{w.insight}.</p>
          </div>
        ))}
      </div>
    </Shell>
  );
}
