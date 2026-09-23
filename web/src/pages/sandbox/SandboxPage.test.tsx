import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { listThreads } from "@/api/agent";
import { listSandboxWorkspace } from "@/api/sandbox";
import SandboxPage from "@/pages/sandbox/SandboxPage";
import { installBrowserStubs } from "@/test/browserStubs";

vi.mock("@/api/agent", () => ({ listThreads: vi.fn() }));
vi.mock("@/api/sandbox", () => ({ listSandboxWorkspace: vi.fn() }));

afterEach(cleanup);

beforeEach(() => {
  vi.mocked(listThreads).mockResolvedValue({
    items: [{
      thread_id: "thread-1",
      title: "Sandbox conversation",
      summary: null,
      agent_id: "leader",
      metadata: {},
      created_at: "2026-09-21T00:00:00Z",
      updated_at: "2026-09-21T00:00:00Z",
      last_message_at: null,
    }],
    next_cursor: null,
    has_more: false,
  });
  vi.mocked(listSandboxWorkspace).mockImplementation(async (_threadId, path = "/workspace") => ({
    thread_id: "thread-1",
    sandbox_id: "s2c-real",
    status: "running",
    path,
    entries: path === "/workspace/outputs"
      ? [
          { name: "analysis-report.md", path: "/workspace/outputs/analysis-report.md", kind: "file", size: 42, modified_at: "2026-09-21T00:00:00Z", file_type: "document" },
          { name: "scene-summary.json", path: "/workspace/outputs/scene-summary.json", kind: "file", size: 18, modified_at: "2026-09-21T00:00:00Z", file_type: "data" },
        ]
      : [
          { name: "outputs", path: "/workspace/outputs", kind: "directory", size: null, modified_at: "2026-09-21T00:00:00Z" },
          { name: "README.md", path: "/workspace/README.md", kind: "file", size: 10, modified_at: "2026-09-21T00:00:00Z", file_type: "document" },
          { name: "scripts", path: "/workspace/scripts", kind: "directory", size: null, modified_at: "2026-09-21T00:00:00Z" },
        ],
  }));
});

it("opens a workspace folder from the real sandbox response", async () => {
  installBrowserStubs();
  render(<SandboxPage />);

  const outputsButtons = await screen.findAllByRole("button", { name: "outputs" });
  fireEvent.click(outputsButtons.at(-1)!);

  expect(await screen.findByText("analysis-report.md")).toBeTruthy();
  expect(screen.getByText("scene-summary.json")).toBeTruthy();
  expect(listSandboxWorkspace).toHaveBeenCalledWith("thread-1", "/workspace/outputs");
});

it("filters entries in the current sandbox folder", async () => {
  installBrowserStubs();
  render(<SandboxPage />);

  await screen.findByText("README.md");

  fireEvent.change(screen.getAllByRole("textbox", { name: "Filter this folder" })[0], {
    target: { value: "readme" },
  });

  await waitFor(() => {
    const fileTable = within(screen.getByRole("table"));
    expect(fileTable.getByText("README.md")).toBeTruthy();
    expect(fileTable.queryByText("scripts")).toBeNull();
  });
});

it("sorts and selects rows in the workspace data table", async () => {
  installBrowserStubs();
  render(<SandboxPage />);

  await screen.findByText("README.md");
  const table = within(screen.getByRole("table"));
  fireEvent.click(table.getByRole("button", { name: "NAME" }));

  const rows = table.getAllByRole("row");
  expect(within(rows[1]).getByText("scripts")).toBeTruthy();

  fireEvent.click(table.getByRole("checkbox", { name: "Select README.md" }));
  expect(screen.getByText("1 of 3 row(s) selected")).toBeTruthy();
});
