import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ComponentType, ReactNode } from "react";
import { toast } from "sonner";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { subjects, teachingAssignments, upload, type COExtractionPreview, type Subject } from "@/lib/api";
import { getStoredSubjectId, storeSubjectId } from "@/lib/subject-context";
import { Route } from "@/routes/faculty.upload";

vi.mock("@/components/lk/Shell", () => ({ Shell: ({ children }: { children: ReactNode }) => children }));
vi.mock("@/components/ui/sonner", () => ({ Toaster: () => null }));

const Page = Route.options.component as ComponentType;
const assigned: Subject[] = ["A", "B"].map((id) => ({
  id, code: id, name: `Subject ${id}`, semester: "1", target_attainment_pct: 60, default_threshold_pct: 60, faculty_user_id: "faculty",
}));
const outcomes = (id: string) => Array.from({ length: 6 }, (_, i) => ({
  id: `${id}-${i}`, subject_id: id, number: i + 1, description: `${id} outcome ${i + 1}`, bloom_name: null, bloom_level: null, threshold_pct: 60, target_attainment_pct: 60,
}));
const preview = (id: string): COExtractionPreview => ({ subject_id: id, count: 6, cos: outcomes(id), saved: false, requires_review: true });
const subjectPicker = () => screen.getByRole("combobox", { name: "Selected subject" });
const switchTo = (value: string) => fireEvent.change(subjectPicker(), { target: { value } });
const chooseFile = () => fireEvent.change(screen.getByLabelText(/Choose syllabus/), { target: { files: [new File(["syllabus"], "a.pdf")] } });

async function openPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  render(<QueryClientProvider client={client}><Page /></QueryClientProvider>);
  await screen.findByText("A outcome 1");
  return client;
}

beforeEach(() => {
  sessionStorage.clear();
  vi.spyOn(subjects, "list").mockResolvedValue(assigned);
  vi.spyOn(subjects, "get").mockImplementation(async (id) => ({ ...assigned.find((s) => s.id === id)!, cos: outcomes(id), modules: [] }));
  vi.spyOn(upload, "getCoverage").mockResolvedValue([]);
  vi.spyOn(teachingAssignments, "list").mockResolvedValue([]);
  vi.spyOn(subjects, "upsertCOs").mockResolvedValue([]);
  vi.spyOn(window, "confirm").mockReturnValue(false);
});
afterEach(() => vi.restoreAllMocks());

it("keeps manual edits and the stored subject on cancel, then discards only on confirmation", async () => {
  storeSubjectId("A");
  await openPage();
  fireEvent.click(screen.getByRole("button", { name: /Enter COs Manually/ }));
  fireEvent.change(screen.getByLabelText("CO1 description"), { target: { value: "Unsaved edit" } });
  switchTo("B");
  expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/discard/i));
  expect(subjectPicker()).toHaveValue("A");
  expect(getStoredSubjectId()).toBe("A");
  expect(screen.getByLabelText("CO1 description")).toHaveValue("Unsaved edit");
  vi.mocked(window.confirm).mockReturnValue(true);
  switchTo("B");
  await screen.findByText("B outcome 1");
  expect(getStoredSubjectId()).toBe("B");
  expect(screen.queryByLabelText("Course Outcome draft")).not.toBeInTheDocument();
  expect(subjects.upsertCOs).not.toHaveBeenCalled();
});

it("keeps the initial subject on list reorder and ignores late extraction after reassignment", async () => {
  let finish!: (result: COExtractionPreview) => void;
  vi.spyOn(subjects, "extractCOs").mockReturnValue(new Promise(resolve => { finish = resolve; }));
  const success = vi.spyOn(toast, "success");
  const client = await openPage();
  chooseFile();
  fireEvent.click(screen.getByRole("button", { name: "Extract Course Outcomes" }));
  expect(subjectPicker()).toBeDisabled();
  switchTo("B");
  expect(subjectPicker()).toHaveValue("A");
  await act(async () => { client.setQueryData(["subjects"], [...assigned].reverse()); });
  expect(subjectPicker()).toHaveValue("A");
  await act(async () => { client.setQueryData(["subjects"], assigned.slice(1)); });
  await screen.findByText("B outcome 1");
  await act(async () => finish(preview("A")));
  expect(subjectPicker()).toBeEnabled();
  expect(screen.queryByLabelText("Course Outcome draft")).not.toBeInTheDocument();
  expect(screen.queryByText("a.pdf")).not.toBeInTheDocument();
  expect(success).not.toHaveBeenCalled();
});

it("rejects a preview labelled for a different subject", async () => {
  vi.spyOn(subjects, "extractCOs").mockResolvedValue(preview("B"));
  await openPage();
  chooseFile();
  fireEvent.click(screen.getByRole("button", { name: "Extract Course Outcomes" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/different subject/i));
  expect(screen.queryByLabelText("Course Outcome draft")).not.toBeInTheDocument();
});

it("protects the selected syllabus and extracted draft, then switches freely once clean", async () => {
  vi.spyOn(subjects, "extractCOs").mockResolvedValue(preview("A"));
  await openPage();
  chooseFile();
  switchTo("B");
  expect(subjectPicker()).toHaveValue("A");
  expect(screen.getByText("a.pdf")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Extract Course Outcomes" }));
  await screen.findByLabelText("CO1 description");
  switchTo("B");
  expect(screen.getByLabelText("CO1 description")).toHaveValue("A outcome 1");
  vi.mocked(window.confirm).mockReturnValueOnce(true);
  switchTo("B");
  await screen.findByText("B outcome 1");
  expect(screen.queryByText("a.pdf")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Course Outcome draft")).not.toBeInTheDocument();
  vi.mocked(window.confirm).mockClear();
  switchTo("A");
  expect(subjectPicker()).toHaveValue("A");
  expect(window.confirm).not.toHaveBeenCalled();
});

it("binds an in-flight save to its original subject without clearing the next editor", async () => {
  let finish!: (saved: ReturnType<typeof outcomes>) => void;
  vi.mocked(subjects.upsertCOs).mockReturnValue(new Promise(resolve => { finish = resolve; }));
  vi.mocked(window.confirm).mockReturnValue(true);
  const client = await openPage();
  fireEvent.click(screen.getByRole("button", { name: /Enter COs Manually/ }));
  fireEvent.click(screen.getByRole("button", { name: /Approve & Save/ }));
  expect(subjectPicker()).toBeDisabled();
  switchTo("B");
  expect(subjectPicker()).toHaveValue("A");
  expect(subjects.upsertCOs).toHaveBeenCalledExactlyOnceWith("A", { cos: expect.arrayContaining([expect.objectContaining({description: "A outcome 1"})]) });
  await act(async () => { client.setQueryData(["subjects"], assigned.slice(1)); });
  await screen.findByText("B outcome 1");
  fireEvent.click(screen.getByRole("button", { name: /Enter COs Manually/ }));
  await act(async () => finish(outcomes("A")));
  expect(screen.getByLabelText("CO1 description")).toHaveValue("B outcome 1");
  expect(client.getQueryState(["subject-detail", "A"])?.isInvalidated).toBe(true);
  expect(client.getQueryState(["subject-detail", "B"])?.isInvalidated).toBe(false);
});
