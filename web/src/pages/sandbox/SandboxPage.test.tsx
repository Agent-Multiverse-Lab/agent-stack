import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { listThreads } from "@/api/thread";
import { deleteSandboxFile, listSandboxWorkspace, readSandboxFile, renameSandboxFile, updateSandboxFile } from "@/api/sandbox";
import SandboxPage from "@/pages/sandbox/SandboxPage";
import { installBrowserStubs } from "@/test/browserStubs";

vi.mock("@/api/thread", () => ({ listThreads: vi.fn() }));
vi.mock("@/api/sandbox", () => ({
  listSandboxWorkspace: vi.fn(),
  readSandboxFile: vi.fn(),
  renameSandboxFile: vi.fn(),
  deleteSandboxFile: vi.fn(),
  updateSandboxFile: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(renameSandboxFile).mockResolvedValue({ path: "/workspace/renamed.md" });
  vi.mocked(deleteSandboxFile).mockResolvedValue(undefined);
  vi.mocked(updateSandboxFile).mockResolvedValue(undefined);
  installBrowserStubs();
  Object.defineProperty(Element.prototype, "getAnimations", { configurable: true, value: () => [] });
  vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(1000);
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(700);
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 1000, bottom: 700, width: 1000, height: 700, toJSON: () => ({}) });
  vi.stubGlobal("ResizeObserver", class {
    constructor(private callback: ResizeObserverCallback) {}
    observe(target: Element) {
      this.callback([{ target, borderBoxSize: [{ inlineSize: 1000, blockSize: 700 }], contentBoxSize: [{ inlineSize: 1000, blockSize: 700 }], devicePixelContentBoxSize: [{ inlineSize: 1000, blockSize: 700 }], contentRect: target.getBoundingClientRect() }], this as unknown as ResizeObserver);
    }
    unobserve() {}
    disconnect() {}
  });
  vi.mocked(listThreads).mockResolvedValue({
    items: [{
      thread_id: "thread-1",
      title: "Sandbox conversation",
      summary: null,
      agent_id: "leader",
      metadata: {},
      created_at: "2026-09-21T00:00:00Z",
      updated_at: "2026-09-21T00:00:00Z",
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
      : path === "/workspace/scripts" ? [] : [
          { name: "outputs", path: "/workspace/outputs", kind: "directory", size: null, modified_at: "2026-09-21T00:00:00Z" },
          { name: "notes.txt", path: "/workspace/notes.txt", kind: "file", size: 8, modified_at: "2026-09-21T00:00:00Z", file_type: "document" },
          { name: "README.md", path: "/workspace/README.md", kind: "file", size: 10, modified_at: "2026-09-21T00:00:00Z", file_type: "document" },
          { name: "scripts", path: "/workspace/scripts", kind: "directory", size: null, modified_at: "2026-09-21T00:00:00Z" },
        ],
  }));
  vi.mocked(readSandboxFile).mockImplementation(async (_threadId, path) => ({
    thread_id: "thread-1",
    sandbox_id: "s2c-real",
    path,
    content: path.endsWith("README.md") ? "# Sandbox readme\n\nHello **world**." : "Notes content",
    encoding: "utf-8",
    truncated: false,
  }));
});

it("opens a workspace folder from the real sandbox response", async () => {
  render(<SandboxPage />);
  const outputs = await screen.findAllByRole("button", { name: "outputs" });
  fireEvent.click(outputs.at(-1)!);
  expect(await screen.findByText("analysis-report.md")).toBeTruthy();
  expect(screen.getByText("scene-summary.json")).toBeTruthy();
  expect(listSandboxWorkspace).toHaveBeenCalledWith("thread-1", "/workspace/outputs");
});

it("filters the flat file list", async () => {
  render(<SandboxPage />);
  await screen.findByText("README.md");
  fireEvent.click(screen.getByRole("button", { name: "Filter this folder" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Filter this folder" }), { target: { value: "readme" } });
  const files = within(screen.getByRole("list", { name: "Workspace files" }));
  expect(files.getByText("README.md")).toBeTruthy();
  expect(files.queryByText("scripts")).toBeNull();
  expect(files.queryByText("notes.txt")).toBeNull();
});

it("switches files inside the same non-modal drawer and closes it", async () => {
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "README.md" }));
  expect(await screen.findByRole("heading", { name: "Sandbox readme" })).toBeTruthy();
  const drawer = screen.getByRole("dialog", { name: "README.md" });
  expect(drawer.getAttribute("aria-modal")).not.toBe("true");
  fireEvent.click(screen.getByRole("button", { name: "notes.txt" }));
  expect(await screen.findByText("Notes content")).toBeTruthy();
  expect(screen.getByRole("dialog", { name: "notes.txt" })).toBe(drawer);
  fireEvent.click(screen.getByRole("button", { name: "Close preview" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(screen.getByRole("list", { name: "Workspace files" })).toBeTruthy();
});

it("previews markdown and its source", async () => {
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "README.md" }));
  expect(await screen.findByRole("heading", { name: "Sandbox readme" })).toBeTruthy();
  expect(readSandboxFile).toHaveBeenCalledWith("thread-1", "/workspace/README.md");
  fireEvent.click(screen.getByRole("tab", { name: "Source code" }));
  await waitFor(() => expect(document.querySelector("pre code")?.textContent).toBe("# Sandbox readme\n\nHello **world**."));
});

it("does not replace a newer preview with a late file response", async () => {
  let finish!: (value: Awaited<ReturnType<typeof readSandboxFile>>) => void;
  vi.mocked(readSandboxFile).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "README.md" }));
  await waitFor(() => expect(readSandboxFile).toHaveBeenCalledWith("thread-1", "/workspace/README.md"));
  fireEvent.click(screen.getByRole("button", { name: "notes.txt" }));
  expect(await screen.findByText("Notes content")).toBeTruthy();
  await act(async () => finish({ thread_id: "thread-1", sandbox_id: "sandbox", path: "/workspace/README.md", content: "Stale content", encoding: "utf-8", truncated: false }));
  expect(screen.queryByText("Stale content")).toBeNull();
  expect(screen.getByText("Notes content")).toBeTruthy();
});

it("ignores a late directory response after navigating elsewhere", async () => {
  let finish!: (value: Awaited<ReturnType<typeof listSandboxWorkspace>>) => void;
  render(<SandboxPage />);
  await screen.findByText("README.md");
  vi.mocked(listSandboxWorkspace).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  fireEvent.click(screen.getAllByRole("button", { name: "outputs" })[0]);
  await waitFor(() => expect(listSandboxWorkspace).toHaveBeenCalledWith("thread-1", "/workspace/outputs"));
  fireEvent.click(screen.getByRole("button", { name: "scripts" }));
  await waitFor(() => expect(listSandboxWorkspace).toHaveBeenCalledWith("thread-1", "/workspace/scripts"));
  await screen.findByText("This folder is empty");
  await act(async () => finish({ thread_id: "thread-1", sandbox_id: "sandbox", status: "running", path: "/workspace/outputs", entries: [{ name: "late.txt", path: "/workspace/outputs/late.txt", kind: "file", size: 4, modified_at: "" }] }));
  expect(screen.queryByText("late.txt")).toBeNull();
});

it("retries a directory error using refresh", async () => {
  vi.mocked(listSandboxWorkspace).mockRejectedValueOnce(new Error("Sandbox unavailable"));
  render(<SandboxPage />);
  expect(await screen.findByRole("alert")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Refresh workspace" }));
  expect(await screen.findByText("README.md")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("shows a file read error inside the drawer", async () => {
  vi.mocked(readSandboxFile).mockRejectedValueOnce(new Error("Binary preview is unavailable"));
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "README.md" }));
  expect(await screen.findByText("Binary preview is unavailable")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Close preview" })).toBeTruthy();
});

it("does not request a sandbox without a conversation", async () => {
  vi.mocked(listThreads).mockResolvedValue({ items: [], next_cursor: null, has_more: false });
  render(<SandboxPage />);
  expect(await screen.findByText("No conversations")).toBeTruthy();
  expect(listSandboxWorkspace).not.toHaveBeenCalled();
});

it("resizes the preview with the shadcn keyboard handle", async () => {
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "README.md" }));
  await screen.findByRole("heading", { name: "Sandbox readme" });
  const handle = screen.getByRole("separator", { name: "Resize preview" });
  const before = handle.getAttribute("aria-valuenow");
  expect(before).not.toBeNull();
  fireEvent.keyDown(handle, { key: "ArrowLeft" });
  await waitFor(() => expect(handle.getAttribute("aria-valuenow")).not.toBe(before));
});

it("expands the preview across the file area and restores or closes it", async () => {
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "README.md" }));
  await screen.findByRole("heading", { name: "Sandbox readme" });
  const files = document.getElementById("sandbox-files")!;
  const preview = document.getElementById("sandbox-preview")!;

  fireEvent.click(screen.getByRole("button", { name: "Expand preview" }));
  await waitFor(() => expect(files.style.flexGrow).toBe("0"));
  expect(preview.style.flexGrow).toBe("100");

  fireEvent.click(screen.getByRole("button", { name: "Restore preview width" }));
  await waitFor(() => expect(Number(files.style.flexGrow)).toBeGreaterThan(0));
  expect(Number(preview.style.flexGrow)).toBeGreaterThan(0);

  fireEvent.click(screen.getByRole("button", { name: "Close preview" }));
  await waitFor(() => expect(preview.style.flexGrow).toBe("0"));
});

it("opens file actions without opening the preview or offering folder deletion", async () => {
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "File actions: README.md" }));
  expect(await screen.findByRole("menuitem", { name: "Rename" })).toBeTruthy();
  expect(screen.getByRole("menuitem", { name: "Edit content" })).toBeTruthy();
  expect(screen.getByRole("menuitem", { name: "Delete" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "File actions: outputs" })).toBeNull();
  expect(readSandboxFile).not.toHaveBeenCalled();
});

it("renames a file and updates its open preview", async () => {
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "README.md" }));
  await screen.findByRole("heading", { name: "Sandbox readme" });
  fireEvent.click(screen.getByRole("button", { name: "File actions: README.md" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }));
  const dialog = screen.getByRole("dialog", { name: "Rename file" });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "File name" }), { target: { value: "renamed.md" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
  await waitFor(() => expect(renameSandboxFile).toHaveBeenCalledWith("thread-1", "/workspace/README.md", "renamed.md"));
  expect(await screen.findByRole("dialog", { name: "renamed.md" })).toBeTruthy();
  await waitFor(() => expect(listSandboxWorkspace).toHaveBeenCalledTimes(2));
  expect(readSandboxFile).toHaveBeenCalledWith("thread-1", "/workspace/renamed.md");
});

it("requires deletion confirmation, retains errors, and closes the deleted preview", async () => {
  vi.mocked(deleteSandboxFile).mockRejectedValueOnce(new Error("File not found"));
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "README.md" }));
  await screen.findByRole("heading", { name: "Sandbox readme" });
  const preview = screen.getByRole("dialog", { name: "README.md" });
  fireEvent.click(screen.getByRole("button", { name: "File actions: README.md" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }));
  expect(deleteSandboxFile).not.toHaveBeenCalled();
  const dialog = screen.getByRole("dialog", { name: "Delete file" });
  fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
  expect(await within(dialog).findByRole("alert")).toHaveProperty("textContent", "File not found");
  expect(preview.isConnected).toBe(true);
  fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(deleteSandboxFile).toHaveBeenLastCalledWith("thread-1", "/workspace/README.md");
  await waitFor(() => expect(listSandboxWorkspace).toHaveBeenCalledTimes(2));
});

it("loads complete editor content and saves with the original version", async () => {
  let content = "First line\r\n";
  vi.mocked(readSandboxFile).mockImplementation(async (_threadId, path) => ({
    thread_id: "thread-1", sandbox_id: "s2c-real", path, content, encoding: "utf-8", truncated: false,
  }));
  vi.mocked(updateSandboxFile).mockImplementation(async (_threadId, _path, draft) => { content = draft; });
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "File actions: README.md" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "Edit content" }));
  const editor = await screen.findByRole("textbox", { name: "File content" });
  expect(readSandboxFile).toHaveBeenCalledWith("thread-1", "/workspace/README.md", true);
  expect(editor).toHaveProperty("value", "First line\n");
  fireEvent.change(editor, { target: { value: "Second line\n" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(updateSandboxFile).toHaveBeenCalledWith("thread-1", "/workspace/README.md", "Second line\n", "First line\r\n"));
  await waitFor(() => expect(screen.queryByRole("textbox", { name: "File content" })).toBeNull());
  expect(await screen.findByText("Second line")).toBeTruthy();
});

it("retains the draft on a save conflict", async () => {
  vi.mocked(updateSandboxFile).mockRejectedValueOnce(new Error("File changed. Reopen it before saving"));
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "File actions: notes.txt" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "Edit content" }));
  fireEvent.change(await screen.findByRole("textbox", { name: "File content" }), { target: { value: "New draft" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "File changed. Reopen it before saving");
  expect(screen.getByRole("textbox", { name: "File content" })).toHaveProperty("value", "New draft");
});

it("cannot save a truncated editor response", async () => {
  vi.mocked(readSandboxFile).mockResolvedValue({
    thread_id: "thread-1", sandbox_id: "s2c-real", path: "/workspace/README.md",
    content: "Partial content", encoding: "utf-8", truncated: true,
  });
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "File actions: README.md" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "Edit content" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "This file is too large to edit");
  expect(screen.getByRole("button", { name: "Save" })).toHaveProperty("disabled", true);
  expect(updateSandboxFile).not.toHaveBeenCalled();
});

it("does not discard a different file's editor when a previous save finishes", async () => {
  let finish!: () => void;
  vi.mocked(updateSandboxFile).mockImplementationOnce(() => new Promise<void>((resolve) => { finish = resolve; }));
  render(<SandboxPage />);
  fireEvent.click(await screen.findByRole("button", { name: "File actions: notes.txt" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "Edit content" }));
  fireEvent.change(await screen.findByRole("textbox", { name: "File content" }), { target: { value: "Saved notes" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(updateSandboxFile).toHaveBeenCalled());
  fireEvent.click(screen.getByRole("button", { name: "File actions: README.md" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "Edit content" }));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "File content" })).toHaveProperty("value", "# Sandbox readme\n\nHello **world**."));
  await act(async () => finish());
  expect(screen.getByRole("textbox", { name: "File content" })).toHaveProperty("value", "# Sandbox readme\n\nHello **world**.");
});
