import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ComponentType, ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { agent, questions, subjects, type Question, type SubjectDetail } from "@/lib/api";
import { Route } from "@/routes/faculty.review";

vi.mock("@/components/lk/Shell", () => ({ Shell: ({ children }: { children: ReactNode }) => children }));
vi.mock("@/components/ui/sonner", () => ({ Toaster: () => null }));

const Page = Route.options.component as ComponentType;
const detail: SubjectDetail = {
  id: "s", name: "Systems", code: "SYS", semester: "1", target_attainment_pct: 60,
  default_threshold_pct: 60, faculty_user_id: "f", cos: [],
  modules: [{ id: "m1", subject_id: "s", number: 1, title: "Memory", processing_status: "processed",
    ppt_file_path: null, processed_at: null, processing_error: null }],
};

function openPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Page /></QueryClientProvider>);
}

beforeEach(() => {
  sessionStorage.clear();
  vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockImplementation(async () =>
    Response.json({ question_ids: ["draft-id"] })));
  vi.spyOn(subjects, "list").mockResolvedValue([detail]);
  vi.spyOn(subjects, "get").mockResolvedValue(detail);
  vi.spyOn(questions, "list").mockResolvedValue([]);
  vi.spyOn(agent, "chat").mockResolvedValue({ conversation_id: "c", reply: "Drafted", proposals: [],
    drafts: [], tool_calls: [{ name: "generate_quiz", status: "draft_review" }] });
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it.each([1, 20])("requests %i drafts directly without choosing or sending a CO", async (count) => {
  openPage();
  const modulePicker = await screen.findByRole("combobox", { name: /^Module/ });
  await waitFor(() => expect(modulePicker).toHaveTextContent("Memory"));
  expect(screen.queryByRole("combobox", { name: /^Course Outcome/ })).not.toBeInTheDocument();
  const generate = screen.getByRole("button", { name: "Generate question drafts" });
  expect(generate).toBeDisabled();
  fireEvent.change(modulePicker, { target: { value: "m1" } });
  fireEvent.change(screen.getByRole("combobox", { name: /^Difficulty/ }), { target: { value: "hard" } });
  const input = screen.getByRole("spinbutton");
  for (const value of ["", "0", "1.5", "21"]) {
    fireEvent.change(input, { target: { value } });
    expect(generate).toBeDisabled();
    fireEvent.click(generate);
    expect(fetch).not.toHaveBeenCalled();
    expect(agent.chat).not.toHaveBeenCalled();
  }
  fireEvent.change(input, { target: { value: String(count) } });
  fireEvent.click(generate);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  const [url, options] = vi.mocked(fetch).mock.calls[0]!;
  expect(String(url)).toMatch(/\/modules\/m1\/question-drafts$/);
  expect(options?.method).toBe("POST");
  expect(JSON.parse(String(options?.body))).toEqual({ difficulty: "hard", count });
  expect(agent.chat).not.toHaveBeenCalled();
  await waitFor(() => expect(questions.list).toHaveBeenCalledTimes(2));
});

const mapped: Question = {
  id: "mapped", module_id: "m1", co_id: "outcome", co_number: 2, stem: "Mapped question?",
  options: ["Yes", "No"], correct_option: 0, explanation: null, marks: 1, difficulty: "easy",
  bloom_level: null, status: "draft", source: "ai", created_by: null,
};
const unmapped: Question = { ...mapped, id: "unmapped", co_id: null, co_number: null, stem: "Unmapped question?" };

const preview = ["The heart has four chambers.", "Valves prevent backflow."];
const mismatch = () => Response.json({ error: {
  code: "MODULE_CONTENT_MISMATCH", message: "Slide content may not match Memory.",
  details: { confirmation_token: "faculty-token", slide_preview: preview },
} }, { status: 409 });

async function requestDrafts() {
  openPage();
  const picker = await screen.findByRole("combobox", { name: /^Module/ });
  await waitFor(() => expect(picker).toHaveTextContent("Memory"));
  fireEvent.change(picker, { target: { value: "m1" } });
  fireEvent.click(screen.getByRole("button", { name: "Generate question drafts" }));
}

it("waits for explicit approval of the displayed slides before posting once with the token", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(mismatch());
  await requestDrafts();
  const alert = within(await screen.findByRole("alert"));
  expect(alert.getByText("Slide content may not match Memory.")).toBeInTheDocument();
  for (const line of preview) expect(alert.getByText(line)).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(questions.list).toHaveBeenCalledTimes(1);
  const confirm = alert.getByRole("button", { name: /generate anyway/i });
  fireEvent.click(confirm);
  fireEvent.click(confirm);
  await waitFor(() => expect(questions.list).toHaveBeenCalledTimes(2));
  expect(fetch).toHaveBeenCalledTimes(2);
  const [[firstUrl], [secondUrl, options]] = vi.mocked(fetch).mock.calls;
  expect(secondUrl).toBe(firstUrl);
  expect(options?.method).toBe("POST");
  expect(JSON.parse(String(options?.body))).toEqual({ difficulty: "medium", count: 5, confirmation_token: "faculty-token" });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("cancels without a request and starts fresh on the next generation", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(mismatch());
  await requestDrafts();
  fireEvent.click(within(await screen.findByRole("alert")).getByRole("button", { name: /cancel/i }));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Generate question drafts" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(JSON.parse(String(vi.mocked(fetch).mock.calls[1]?.[1]?.body))).toEqual({ difficulty: "medium", count: 5 });
});

function openReview(bank: Question[]) {
  vi.mocked(subjects.get).mockResolvedValue({ ...detail, cos: [{ id: "outcome", subject_id: "s",
    number: 2, description: "Explain paging", threshold_pct: 60, target_attainment_pct: 60, bloom_level: null, bloom_name: null }] });
  vi.mocked(questions.list).mockResolvedValue(bank);
  vi.spyOn(questions, "approve").mockResolvedValue({ ...mapped, status: "approved" });
  openPage();
}

it("requires a saved mapping before an unmapped draft can be approved", async () => {
  const saved = { ...unmapped, co_id: mapped.co_id, co_number: mapped.co_number };
  vi.spyOn(questions, "update").mockImplementation(async () => {
    vi.mocked(questions.list).mockResolvedValue([saved]);
    return saved;
  });
  openReview([unmapped]);
  const card = within(await screen.findByRole("article"));
  expect(card.getByText("Unmapped CO")).toBeInTheDocument();
  const approve = card.getByRole("button", { name: "Approve" });
  expect(approve).toBeDisabled();
  expect(screen.getByRole("button", { name: /Approve all visible/ })).toBeDisabled();
  expect(card.getByRole("button", { name: "Reject" })).toBeEnabled();
  fireEvent.click(approve);
  expect(questions.approve).not.toHaveBeenCalled();
  fireEvent.click(card.getByRole("button", { name: "Edit" }));
  const picker = card.getByRole("combobox", { name: /^Course Outcome mapping/ });
  expect(picker).toHaveValue("");
  const save = card.getByRole("button", { name: "Save changes" });
  expect(save).toBeDisabled();
  fireEvent.change(picker, { target: { value: "outcome" } });
  expect(approve).toBeDisabled();
  fireEvent.click(save);
  await waitFor(() => expect(approve).toBeEnabled());
  expect(questions.update).toHaveBeenCalledWith(unmapped.id, expect.objectContaining({ co_id: "outcome" }));
  expect(card.getByText("CO2")).toBeInTheDocument();
  fireEvent.click(card.getByRole("button", { name: "Edit" }));
  expect(card.getByRole("combobox", { name: /^Course Outcome mapping/ })).toHaveValue("outcome");
  fireEvent.click(card.getByRole("button", { name: "Cancel" }));
  fireEvent.click(approve);
  await waitFor(() => expect(questions.approve).toHaveBeenCalledExactlyOnceWith(unmapped.id));
});

it("does not approve the old CO while its replacement is being edited", async () => {
  openReview([mapped]);
  const card = within(await screen.findByRole("article"));
  fireEvent.click(card.getByRole("button", { name: "Edit" }));
  expect(card.getByRole("button", { name: "Approve" })).toBeDisabled();
  expect(screen.getByRole("button", { name: /Approve all visible/ })).toBeDisabled();
  fireEvent.click(card.getByRole("button", { name: "Cancel" }));
  expect(card.getByRole("button", { name: "Approve" })).toBeEnabled();
});

it("bulk approves only visible, mapped drafts", async () => {
  openReview([mapped, unmapped, { ...mapped, id: "approved", status: "approved" },
    { ...mapped, id: "hidden", difficulty: "hard" }]);
  await screen.findByText(unmapped.stem);
  fireEvent.change(screen.getByLabelText("Filter by difficulty"), { target: { value: "easy" } });
  fireEvent.click(screen.getByRole("button", { name: /Approve all visible/ }));
  await waitFor(() => expect(questions.approve).toHaveBeenCalledExactlyOnceWith(mapped.id));
});
