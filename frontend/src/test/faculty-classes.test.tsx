import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType, ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { Route } from "@/routes/faculty.upload";
import { Route as AnalyticsRoute } from "@/routes/faculty.analytics";

const api = vi.hoisted(() => ({
  list: vi.fn(),
  roster: vi.fn(),
  attempts: vi.fn(),
  attainment: vi.fn(),
}));
const courses = vi.hoisted(() => ({ list: vi.fn(), get: vi.fn() }));
const sheets = vi.hoisted(() => ({ getSheet: vi.fn(), getWeakCOs: vi.fn(), getSummary: vi.fn() }));
vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  teachingAssignments: api,
  subjects: courses,
  coSheet: sheets,
  upload: { getCoverage: async () => [] },
}));
vi.mock("@/components/lk/Shell", () => ({
  Shell: ({ children }: { children: ReactNode }) => children,
}));
vi.mock("@/components/ui/sonner", () => ({ Toaster: () => null }));

const subject = { id: "s", code: "CS", name: "Computing" };
const other = { id: "t", code: "MA", name: "Math" };
const cos = Array.from({ length: 6 }, (_, i) => ({
  id: `co${i}`,
  number: i + 1,
  description: `Shared outcome ${i + 1}`,
}));
const classes = [
  { id: "a", subject_id: "s", section: "A", status: "active" },
  { id: "b", subject_id: "s", section: "B", status: "active" },
  { id: "old", subject_id: "s", section: "A", status: "archived" },
  { id: "other", subject_id: "t", section: "Other", status: "active" },
];
const roster = (id: string) => ({
  teaching_assignment: classes.find((c) => c.id === id),
  students: [{ student_id: id, name: `Student ${id}`, usn: `U${id}` }],
  total_students: 1,
});
function open(route: typeof Route | typeof AnalyticsRoute) {
  const Page = route.options.component as ComponentType;
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  render(
    <QueryClientProvider client={client}>
      <Page />
    </QueryClientProvider>,
  );
}
async function selectClass(id: string) {
  const option = await screen.findByRole("option", {
    name: id === "a" ? "Section A" : "Section B",
  });
  fireEvent.change(option.closest("select")!, { target: { value: id } });
}
beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  courses.list.mockResolvedValue([subject, other]);
  courses.get.mockImplementation(async (id) => ({
    ...(id === "s" ? subject : other),
    cos,
    modules: [],
  }));
  api.list.mockResolvedValue(classes);
  api.roster.mockImplementation(async (id) => roster(id));
  api.attempts.mockImplementation(async (id) => [
    {
      teaching_assignment_id: id,
      subject_id: "s",
      attempt_id: id,
      quiz_title: `Quiz ${id}`,
      student_name: `Learner ${id}`,
      attempt_number: 1,
    },
  ]);
  api.attainment.mockImplementation(async (id) => ({
    teaching_assignment_id: id,
    subject_id: "s",
    cos: cos.map((co) => ({ ...co, attainment_pct: id === "a" ? 20 : 80 })),
  }));
  sheets.getSheet.mockResolvedValue({ columns: [], rows: [], averages: {} });
  sheets.getWeakCOs.mockResolvedValue([]);
  sheets.getSummary.mockResolvedValue([]);
});

it("switches section reports by assignment ID without resetting the subject's six COs or its draft", async () => {
  open(Route);
  await screen.findByText("Shared outcome 1");
  fireEvent.click(screen.getByRole("button", { name: /Enter COs Manually/ }));
  fireEvent.change(screen.getByLabelText("CO1 description"), {
    target: { value: "Unsaved subject edit" },
  });
  await selectClass("a");
  expect(
    screen.queryByRole("option", { name: /Other.*section|Section Other/i }),
  ).not.toBeInTheDocument();
  expect(await screen.findByText("Student a")).toBeInTheDocument();
  expect(await screen.findByText("Quiz a")).toBeInTheDocument();
  expect(screen.getAllByText("20%")).toHaveLength(6);
  await selectClass("b");
  expect(await screen.findByText("Student b")).toBeInTheDocument();
  expect(await screen.findByText("Quiz b")).toBeInTheDocument();
  expect(screen.queryByText("Student a")).not.toBeInTheDocument();
  expect(screen.queryByText("Quiz a")).not.toBeInTheDocument();
  expect(screen.getAllByText("80%")).toHaveLength(6);
  expect(screen.getByLabelText("CO1 description")).toHaveValue("Unsaved subject edit");
  expect(
    within(screen.getByLabelText("Course Outcome draft")).getAllByRole("textbox"),
  ).toHaveLength(6);
  expect(courses.get).toHaveBeenCalledTimes(1);
});

it("does not display an earlier section's late roster or keep its selection after a subject switch", async () => {
  let finish!: (value: ReturnType<typeof roster>) => void;
  api.roster.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  open(Route);
  await selectClass("a");
  await selectClass("b");
  await screen.findByText("Student b");
  await act(async () => finish(roster("a")));
  expect(screen.queryByText("Student a")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Selected subject"), { target: { value: "t" } });
  await screen.findByRole("option", { name: "Section Other" });
  expect(screen.getByLabelText("Class / section")).toHaveValue("");
  expect(screen.queryByText("Student b")).not.toBeInTheDocument();
});

it("shows assignment analytics without exposing a subject-wide sheet or export as a class report", async () => {
  open(AnalyticsRoute);
  const view = await screen.findByLabelText("Report view");
  fireEvent.change(view, { target: { value: "class" } });
  await selectClass("a");
  await screen.findByText("Quiz a");
  expect(screen.getAllByText("20%")).toHaveLength(6);
  expect(screen.queryByRole("button", { name: /Export to Excel/ })).not.toBeInTheDocument();
  expect(screen.queryByText("Average score by CO")).not.toBeInTheDocument();
});

it("distinguishes archived and active classes with the same label", async () => {
  open(Route);
  const option = await screen.findByRole("option", { name: /Section A.*archived/ });
  fireEvent.change(option.closest("select")!, { target: { value: "old" } });
  expect(await screen.findByText("Student old")).toBeInTheDocument();
  expect(await screen.findByText("Quiz old")).toBeInTheDocument();
  expect(api.roster).not.toHaveBeenCalledWith("a");
});

it("does not display a mismatched class response", async () => {
  api.roster.mockResolvedValueOnce(roster("b"));
  open(Route);
  await selectClass("a");
  expect(await screen.findByRole("alert")).toHaveTextContent(/could not load the selected class/i);
  expect(screen.queryByText("Student b")).not.toBeInTheDocument();
});
