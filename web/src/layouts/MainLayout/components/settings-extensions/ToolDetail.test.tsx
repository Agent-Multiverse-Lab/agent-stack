import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import i18n from "@/i18n";
import { installBrowserStubs } from "@/test/browserStubs";
import { SettingsExtensions } from "../SettingsExtensions";
import { ToolSchemaSection } from "./ToolSchemaSection";
import { ToolDetail } from "./ToolDetail";

let fetchSpy: ReturnType<typeof vi.fn>;
let requestSpy: ReturnType<typeof vi.spyOn>;
let storageSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  installBrowserStubs();
  fetchSpy = vi.fn();
  vi.stubGlobal("fetch", fetchSpy);
  requestSpy = vi.spyOn(XMLHttpRequest.prototype, "open");
  storageSpy = vi.spyOn(Storage.prototype, "setItem");
});
afterEach(async () => {
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(requestSpy).not.toHaveBeenCalled();
  expect(storageSpy).not.toHaveBeenCalled();
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  await i18n.changeLanguage("en");
});

function Harness({ onClose = () => {} }: { onClose?: () => void }) {
  return <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
    <DialogContent>
      <DialogTitle>Settings</DialogTitle>
      <DialogDescription>Application settings</DialogDescription>
      <SettingsExtensions kind="mcp" />
    </DialogContent>
  </Dialog>;
}

async function openService() {
  fireEvent.click(screen.getByRole("button", { name: "Explore local preview" }));
  fireEvent.click(screen.getByRole("button", { name: "Document service" }));
  return screen.findByRole("dialog", { name: "Document service" });
}

async function openTool(service: HTMLElement, name = "search_documents") {
  const row = within(service).getByRole("button", { name });
  row.focus();
  fireEvent.click(row);
  return screen.findByRole("dialog", { name });
}

it.each(["Back to tools", "Close", "Escape", "Backdrop"])("closes only ToolDetail with %s and restores the selected card", async (action) => {
  const onClose = vi.fn();
  render(<Harness onClose={onClose} />);
  const service = await openService();
  fireEvent.change(within(service).getByRole("textbox", { name: "Service name" }), { target: { value: "Unapplied service" } });
  fireEvent.click(within(service).getByRole("tab", { name: "Tools" }));
  const card = within(service).getByRole("button", { name: "search_documents" });
  const detail = await openTool(service);
  expect(within(detail).getByText("Example metadata")).toBeTruthy();
  expect(within(detail).getByText("Search documents by keyword and optional collection.")).toBeTruthy();
  expect(within(detail).getByRole("region", { name: "Input schema" }).textContent).toContain('"collection_id"');
  expect(within(detail).getByRole("region", { name: "Output schema" }).textContent).toContain('"documents"');
  expect(within(detail).getAllByRole("button").map((button) => button.textContent?.trim())).toEqual(["Back to tools", "Close"]);
  await waitFor(() => expect(document.activeElement).toBe(within(detail).getByRole("button", { name: "Back to tools" })));
  if (action === "Escape") fireEvent.keyDown(detail, { key: "Escape", code: "Escape" });
  else if (action === "Backdrop") {
    const overlay = [...document.querySelectorAll<HTMLElement>('[data-slot="dialog-overlay"]')]
      .find((element) => element.className.includes("z-[120]"));
    expect(overlay).toBeTruthy();
    fireEvent.mouseDown(overlay!, { button: 0 });
    fireEvent.mouseUp(overlay!, { button: 0 });
    fireEvent.click(overlay!);
  } else fireEvent.click(within(detail).getByRole("button", { name: action }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "search_documents" })).toBeNull());
  await waitFor(() => expect(document.activeElement).toBe(card));
  expect(screen.getByRole("dialog", { name: "Document service" })).toBe(service);
  expect(within(service).getByRole("tab", { name: "Tools" }).getAttribute("aria-selected")).toBe("true");
  expect(screen.queryByRole("dialog", { name: "Discard preview changes?" })).toBeNull();
  expect(onClose).not.toHaveBeenCalled();
  fireEvent.click(within(service).getByRole("tab", { name: "Basic configuration" }));
  expect((within(service).getByRole("textbox", { name: "Service name" }) as HTMLInputElement).value).toBe("Unapplied service");
  fireEvent.keyDown(service, { key: "Escape", code: "Escape" });
  expect(await screen.findByRole("dialog", { name: "Discard preview changes?" })).toBeTruthy();
});

it("opens different tools repeatedly without stale metadata or draft changes", async () => {
  render(<Harness />);
  const service = await openService();
  fireEvent.click(within(service).getByRole("tab", { name: "Tools" }));
  for (const name of ["search_documents", "list_collections", "read_document", "search_documents"]) {
    const detail = await openTool(service, name);
    if (name === "list_collections") {
      expect(within(detail).getByText("No declared parameters")).toBeTruthy();
      expect(within(detail).getByText("Output schema unavailable")).toBeTruthy();
      expect(within(detail).queryByText("Required")).toBeNull();
    } else expect(within(detail).queryByText("Output schema unavailable")).toBeNull();
    fireEvent.click(within(detail).getByRole("button", { name: "Back to tools" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name })).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(within(service).getByRole("button", { name })));
  }
  fireEvent.click(within(service).getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Document service" })).toBeNull());
  expect(screen.queryByRole("dialog", { name: "Discard preview changes?" })).toBeNull();
  expect(screen.getByRole("dialog", { name: "Settings" })).toBeTruthy();
});

it("keeps an empty tool list honest for a new local service", async () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole("button", { name: "Explore local preview" }));
  fireEvent.click(screen.getByRole("button", { name: "Add example MCP service" }));
  const service = await screen.findByRole("dialog", { name: "Add example MCP service" });
  fireEvent.click(within(service).getByRole("tab", { name: "Tools" }));
  expect(within(service).getByText("No example tools")).toBeTruthy();
  expect(within(service).queryByRole("list")).toBeNull();
});

it("renders missing, empty, boolean, nested and untyped schemas without inventing metadata", () => {
  const { rerender } = render(<ToolSchemaSection title="Input schema" emptyMessage="Input schema unavailable" />);
  expect(screen.getByText("Input schema unavailable")).toBeTruthy();
  rerender(<ToolSchemaSection title="Input schema" emptyMessage="Input schema unavailable" schema={{}} />);
  expect(screen.getByText("{}")).toBeTruthy();
  expect(screen.queryByText("Input schema unavailable")).toBeNull();
  expect(screen.queryByText("No declared parameters")).toBeNull();
  rerender(<ToolSchemaSection title="Input schema" emptyMessage="Input schema unavailable" schema={false} />);
  expect(screen.getByText("false")).toBeTruthy();
  rerender(<ToolSchemaSection title="Input schema" emptyMessage="Input schema unavailable" schema={{
    type: "object",
    properties: {
      collection: { type: "object", properties: { ids: { type: "array", items: { type: "string" } } } },
      reference: { $ref: "#/$defs/filter" },
      query: { type: ["string", "null"], description: "Search query" },
    }, required: ["collection"],
  }} />);
  expect(screen.getByText("collection")).toBeTruthy();
  expect(screen.getByText("Type unspecified")).toBeTruthy();
  expect(screen.getByText("string | null")).toBeTruthy();
  expect(screen.getAllByText("Required")).toHaveLength(1);
  expect(screen.getByRole("region").querySelector("pre")?.textContent).toContain('"$ref": "#/$defs/filter"');
  expect(screen.getByRole("region").querySelector("pre")?.textContent).toContain('"items"');
});

it("shows unknown purpose and schemas when no metadata is supplied", async () => {
  render(<ToolDetail tool={{ name: "unknown_tool" }} isOpen returnFocusRef={{ current: null }} fallbackFocusRef={{ current: null }} onClose={() => {}} onClosed={() => {}} />);
  const detail = await screen.findByRole("dialog", { name: "unknown_tool" });
  expect(within(detail).getByText("Description unavailable")).toBeTruthy();
  expect(within(detail).getByText("Input schema unavailable")).toBeTruthy();
  expect(within(detail).getByText("Output schema unavailable")).toBeTruthy();
});

it("translates the tool list, purpose, schemas and navigation in Chinese", async () => {
  // Language selection itself persists; begin mutation assertions after that action.
  await act(async () => { await i18n.changeLanguage("zh-CN"); });
  storageSpy.mockClear();
  render(<Harness />);
  fireEvent.click(screen.getByRole("button", { name: "体验本地预览" }));
  fireEvent.click(screen.getByRole("button", { name: "文档服务" }));
  const service = await screen.findByRole("dialog", { name: "文档服务" });
  fireEvent.click(within(service).getByRole("tab", { name: "工具" }));
  const detail = await openTool(service);
  expect(within(detail).getByText("示例工具信息")).toBeTruthy();
  expect(within(detail).getByText("按关键词搜索文档，可限定文档集合。")).toBeTruthy();
  expect(within(detail).getByRole("region", { name: "输入参数" })).toBeTruthy();
  expect(within(detail).getByRole("region", { name: "输出结构" })).toBeTruthy();
  expect(within(detail).getByRole("button", { name: "返回工具列表" })).toBeTruthy();
});
