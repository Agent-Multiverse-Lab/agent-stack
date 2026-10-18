import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import i18n from "@/i18n";
import { SettingsExtensions } from "./SettingsExtensions";
import { Skill } from "./settings-extensions/Skill";
import { Mcp } from "./settings-extensions/Mcp";
import type { ExtensionKind } from "./settings-extensions/extension-preview-data";
import { installBrowserStubs } from "@/test/browserStubs";

const fetchSpy = vi.fn();
let requestSpy: ReturnType<typeof vi.spyOn>;
let storageSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  installBrowserStubs();
  fetchSpy.mockReset();
  vi.stubGlobal("fetch", fetchSpy);
  requestSpy = vi.spyOn(XMLHttpRequest.prototype, "open");
  storageSpy = vi.spyOn(Storage.prototype, "setItem");
});
afterEach(async () => {
  // Every interaction in this suite must remain entirely in memory.
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(requestSpy).not.toHaveBeenCalled();
  expect(storageSpy).not.toHaveBeenCalled();
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  await i18n.changeLanguage("en");
});

function Harness({ kind = "skills", onClose = () => {} }: { kind?: ExtensionKind; onClose?: () => void }) {
  return <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
    <DialogContent className="z-[101]" overlayClassName="z-[100]">
      <DialogTitle>Settings</DialogTitle>
      <DialogDescription>Application settings</DialogDescription>
      <SettingsExtensions kind={kind} />
    </DialogContent>
  </Dialog>;
}

function enterPreview() {
  fireEvent.click(screen.getByRole("button", { name: "Explore local preview" }));
}
async function openExample(name = "Research brief") {
  const row = screen.getByRole("button", { name });
  row.focus();
  fireEvent.click(row);
  return screen.findByRole("dialog", { name });
}
async function finishClosing(name: string) {
  await waitFor(() => expect(screen.queryByRole("dialog", { name })).toBeNull());
}

it.each(["skills", "mcp"] as const)("keeps %s server-managed with no fabricated installed list", (kind) => {
  render(<Harness kind={kind} />);
  expect(screen.getByText("Management unavailable")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Explore local preview" })).toBeTruthy();
  expect(screen.queryByRole("list")).toBeNull();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("switch")).toBeNull();
  expect(screen.queryByText("Research brief")).toBeNull();
  expect(screen.queryByText("Document service")).toBeNull();
});

it.each([
  { kind: "skills" as const, first: "Research brief", second: "Spatial analysis", field: "Skill name" },
  { kind: "mcp" as const, first: "Document service", second: "Database service", field: "Service name" },
])("opens $kind configuration directly and restores focus through repeated selections", async ({ kind, first, second, field }) => {
  const onClose = vi.fn();
  render(<Harness kind={kind} onClose={onClose} />);
  enterPreview();
  const row = screen.getByRole("button", { name: first });
  let dialog = await openExample(first);
  expect(within(dialog).getAllByText("Local preview · No server changes")).toHaveLength(2);
  expect(within(dialog).queryByText("Changes only last in this preview. Nothing is saved to the server.")).toBeNull();
  expect((within(dialog).getByRole("textbox", { name: field }) as HTMLInputElement).value).toBe(first);
  expect(within(dialog).getByRole("button", { name: "Apply to preview" })).toBeTruthy();
  expect(within(dialog).queryByRole("button", { name: "Edit configuration" })).toBeNull();
  fireEvent.click(within(dialog).getByRole("button", { name: "Back to list" }));
  await finishClosing(first);
  await waitFor(() => expect(document.activeElement).toBe(row));
  dialog = await openExample(second);
  fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
  await finishClosing(second);
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: second })));
  dialog = await openExample(first);
  fireEvent.keyDown(dialog, { key: "Escape", code: "Escape" });
  await finishClosing(first);
  expect(screen.getByRole("dialog", { name: "Settings" })).toBeTruthy();
  expect(onClose).not.toHaveBeenCalled();
});

it("switches SkillDetail tabs without losing drafts or leaving configuration", async () => {
  render(<Harness />);
  enterPreview();
  const configuration = await openExample();
  fireEvent.change(within(configuration).getByRole("textbox", { name: "Skill name" }), { target: { value: "Draft before file" } });
  fireEvent.click(within(configuration).getByRole("tab", { name: "Example file" }));
  expect(screen.getByRole("dialog", { name: "Research brief" })).toBe(configuration);
  expect(within(configuration).getByRole("tab", { name: "Example file" }).getAttribute("aria-selected")).toBe("true");
  expect(within(configuration).getByText("Read only")).toBeTruthy();
  expect(within(configuration).getByText(/This sample is not installed or executed\./)).toBeTruthy();
  expect(within(configuration).queryByRole("textbox")).toBeNull();
  fireEvent.click(within(configuration).getByRole("tab", { name: "Basic configuration" }));
  expect((within(configuration).getByRole("textbox", { name: "Skill name" }) as HTMLInputElement).value).toBe("Draft before file");
  fireEvent.click(within(configuration).getByRole("tab", { name: "Example file" }));
  fireEvent.keyDown(configuration, { key: "Escape", code: "Escape" });
  expect(await screen.findByRole("dialog", { name: "Discard preview changes?" })).toBeTruthy();
});

it.each(["Cancel", "Back to list", "Close", "Escape", "Backdrop"])("guards dirty %s, keeps the draft on cancellation, and discards only after confirmation", async (action) => {
  const onClose = vi.fn();
  render(<Harness onClose={onClose} />);
  enterPreview();
  const row = screen.getByRole("button", { name: "Research brief" });
  const configuration = await openExample();
  const name = within(configuration).getByRole("textbox", { name: "Skill name" });
  fireEvent.change(name, { target: { value: "Unapplied name" } });
  name.focus();
  const dismiss = () => {
    if (action === "Escape") fireEvent.keyDown(configuration, { key: "Escape", code: "Escape" });
    else if (action === "Backdrop") {
      const overlay = [...document.querySelectorAll<HTMLElement>('[data-slot="dialog-overlay"]')]
        .find((element) => element.className.includes("z-[110]"));
      expect(overlay).toBeTruthy();
      fireEvent.mouseDown(overlay!, { button: 0 });
      fireEvent.mouseUp(overlay!, { button: 0 });
      fireEvent.click(overlay!);
    } else fireEvent.click(within(configuration).getByRole("button", { name: action }));
  };
  dismiss();
  let confirm = await screen.findByRole("dialog", { name: "Discard preview changes?" });
  fireEvent.click(within(confirm).getByRole("button", { name: "Keep editing" }));
  await finishClosing("Discard preview changes?");
  await waitFor(() => expect(document.activeElement).toBe(name));
  expect((name as HTMLInputElement).value).toBe("Unapplied name");
  expect(onClose).not.toHaveBeenCalled();
  dismiss();
  confirm = await screen.findByRole("dialog", { name: "Discard preview changes?" });
  fireEvent.keyDown(confirm, { key: "Escape", code: "Escape" });
  await finishClosing("Discard preview changes?");
  expect((name as HTMLInputElement).value).toBe("Unapplied name");
  dismiss();
  confirm = await screen.findByRole("dialog", { name: "Discard preview changes?" });
  fireEvent.click(within(confirm).getByRole("button", { name: "Discard changes" }));
  await finishClosing("Research brief");
  await waitFor(() => expect(document.activeElement).toBe(row));
  expect(screen.getByRole("dialog", { name: "Settings" })).toBeTruthy();
  expect(onClose).not.toHaveBeenCalled();
  const reopened = await openExample();
  expect((within(reopened).getByRole("textbox", { name: "Skill name" }) as HTMLInputElement).value).toBe("Research brief");
});

it("cancels unchanged configuration immediately and Apply returns directly to the list", async () => {
  render(<Harness />);
  enterPreview();
  let configuration = await openExample();
  fireEvent.click(within(configuration).getByRole("button", { name: "Cancel" }));
  await finishClosing("Research brief");
  expect(screen.queryByRole("dialog", { name: "Discard preview changes?" })).toBeNull();
  configuration = await openExample();
  fireEvent.change(within(configuration).getByRole("textbox", { name: "Skill name" }), { target: { value: "My preview skill" } });
  fireEvent.click(within(configuration).getByRole("button", { name: "Apply to preview" }));
  await finishClosing("Research brief");
  expect(screen.queryByRole("dialog", { name: "My preview skill" })).toBeNull();
  expect(screen.getByText("Applied to this preview only")).toBeTruthy();
  const row = screen.getByRole("button", { name: "My preview skill" });
  await waitFor(() => expect(document.activeElement).toBe(row));
  const reopened = await openExample("My preview skill");
  expect((within(reopened).getByRole("textbox", { name: "Skill name" }) as HTMLInputElement).value).toBe("My preview skill");
  fireEvent.click(within(reopened).getByRole("button", { name: "Cancel" }));
  await finishClosing("My preview skill");
  expect(screen.queryByRole("dialog", { name: "Discard preview changes?" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Reset preview" }));
  expect(screen.queryByRole("button", { name: "My preview skill" })).toBeNull();
  expect(screen.getByRole("button", { name: "Research brief" })).toBeTruthy();
});

it("filters by name and enabled state, handles empty results and clears filters", () => {
  render(<Harness />);
  enterPreview();
  fireEvent.click(screen.getByRole("button", { name: /^Disabled/ }));
  expect(screen.queryByRole("button", { name: "Research brief" })).toBeNull();
  expect(screen.getByRole("button", { name: "Writing review" })).toBeTruthy();
  fireEvent.change(screen.getByRole("textbox", { name: "Search example skills" }), { target: { value: "no such example" } });
  expect(screen.getByText("No matching examples")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(within(screen.getByRole("list", { name: "Example skills" })).getAllByRole("listitem")).toHaveLength(3);
  fireEvent.change(screen.getByRole("textbox", { name: "Search example skills" }), { target: { value: " spatial-ANALYSIS " } });
  expect(within(screen.getByRole("list", { name: "Example skills" })).getAllByRole("listitem")).toHaveLength(1);
});

it("adds only local examples, validates a name, and clears additions on exit", async () => {
  render(<Harness />);
  enterPreview();
  const add = screen.getByRole("button", { name: "Add example skill" });
  fireEvent.click(add);
  const form = await screen.findByRole("dialog", { name: "Add example skill" });
  fireEvent.click(within(form).getByRole("button", { name: "Apply to preview" }));
  expect(screen.getByRole("alert").textContent).toBe("Enter a name for this example.");
  fireEvent.change(within(form).getByRole("textbox", { name: "Skill name" }), { target: { value: "New local skill" } });
  fireEvent.click(within(form).getByRole("button", { name: "Apply to preview" }));
  await finishClosing("Add example skill");
  await waitFor(() => expect(document.activeElement).toBe(add));
  expect(within(screen.getByRole("list", { name: "Example skills" })).getAllByRole("listitem")).toHaveLength(4);
  fireEvent.click(screen.getByRole("button", { name: "Exit preview" }));
  expect(screen.getByText("Management unavailable")).toBeTruthy();
  enterPreview();
  expect(within(screen.getByRole("list", { name: "Example skills" })).getAllByRole("listitem")).toHaveLength(3);
  expect(screen.queryByText("New local skill")).toBeNull();
});

it("never accepts credentials or fabricates MCP connection or tool discovery results", async () => {
  render(<Harness kind="mcp" />);
  enterPreview();
  const configuration = await openExample("Document service");
  fireEvent.click(within(configuration).getByRole("tab", { name: /^Tools/ }));
  expect(within(configuration).getByRole("list", { name: "Example tools" })).toBeTruthy();
  fireEvent.click(within(configuration).getByRole("tab", { name: "Basic configuration" }));
  fireEvent.change(within(configuration).getByRole("textbox", { name: "Service name" }), { target: { value: "Edited preview service" } });
  fireEvent.click(within(configuration).getByRole("tab", { name: "Connection settings" }));
  expect(within(configuration).getByText("Connection not tested")).toBeTruthy();
  expect((within(configuration).getByRole("textbox", { name: "Server address" }) as HTMLInputElement).value).toBe("https://mcp.example.invalid/documents");
  expect(within(configuration).getByText("Credentials are unavailable in local preview. Do not enter secrets.")).toBeTruthy();
  expect(within(configuration).queryByLabelText("Credentials")).toBeNull();
  expect(configuration.querySelector('input[type="password"]')).toBeNull();
  const test = within(configuration).getByRole("button", { name: "Connection testing unavailable" }) as HTMLButtonElement;
  expect(test.disabled).toBe(true);
  fireEvent.click(test);
  fireEvent.click(within(configuration).getByRole("button", { name: "Apply to preview" }));
  await finishClosing("Document service");
  const reopened = await openExample("Edited preview service");
  fireEvent.click(within(reopened).getByRole("tab", { name: "Connection settings" }));
  expect(within(reopened).getByText("Connection not tested")).toBeTruthy();
});

it("resets preview across kinds and remounts without sharing records", async () => {
  const { rerender, unmount } = render(<SettingsExtensions kind="skills" />);
  enterPreview();
  fireEvent.change(screen.getByRole("textbox", { name: "Search example skills" }), { target: { value: "missing" } });
  rerender(<SettingsExtensions kind="mcp" />);
  expect(screen.getByText("Management unavailable")).toBeTruthy();
  enterPreview();
  expect(within(screen.getByRole("list", { name: "Example MCP services" })).getAllByRole("listitem")).toHaveLength(3);
  expect(screen.queryByText("Research brief")).toBeNull();
  await openExample("Document service");
  unmount();
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  render(<SettingsExtensions kind="mcp" />);
  expect(screen.getByText("Management unavailable")).toBeTruthy();
  expect(screen.queryByText("Document service")).toBeNull();
});

it("returns focus to search when Apply removes the opening row from a filter", async () => {
  render(<Harness />);
  enterPreview();
  fireEvent.click(screen.getByRole("button", { name: /^Enabled/ }));
  const configuration = await openExample();
  fireEvent.click(within(configuration).getByRole("switch", { name: "Enabled" }));
  fireEvent.click(within(configuration).getByRole("button", { name: "Apply to preview" }));
  await finishClosing("Research brief");
  expect(screen.queryByRole("button", { name: "Research brief" })).toBeNull();
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("textbox", { name: "Search example skills" })));
});

it("preserves literal user-entered names and descriptions in the Chinese interface", async () => {
  await act(async () => { await i18n.changeLanguage("zh-CN"); });
  storageSpy.mockClear();
  render(<Harness />);
  fireEvent.click(screen.getByRole("button", { name: i18n.t("Explore local preview") }));
  fireEvent.click(screen.getByRole("button", { name: i18n.t("Research brief") }));
  const configuration = await screen.findByRole("dialog", { name: i18n.t("Research brief") });
  const name = within(configuration).getByRole("textbox", { name: i18n.t("Skill name") }) as HTMLInputElement;
  const description = within(configuration).getByRole("textbox", { name: i18n.t("Description") }) as HTMLTextAreaElement;
  fireEvent.change(name, { target: { value: "General" } });
  fireEvent.change(description, { target: { value: "Settings" } });
  expect(name.value).toBe("General");
  expect(description.value).toBe("Settings");
  fireEvent.click(within(configuration).getByRole("button", { name: i18n.t("Apply to preview") }));
  await finishClosing(i18n.t("Research brief"));
  fireEvent.change(screen.getByRole("textbox", { name: i18n.t("Search example skills") }), { target: { value: "General" } });
  fireEvent.click(screen.getByRole("button", { name: "General" }));
  const updated = await screen.findByRole("dialog", { name: "General" });
  expect((within(updated).getByRole("textbox", { name: i18n.t("Description") }) as HTMLTextAreaElement).value).toBe("Settings");
});

it("rejects credential-bearing or invalid MCP addresses and validates additions locally", async () => {
  render(<Harness kind="mcp" />);
  enterPreview();
  fireEvent.click(screen.getByRole("button", { name: "Add example MCP service" }));
  const configuration = await screen.findByRole("dialog", { name: "Add example MCP service" });
  fireEvent.change(within(configuration).getByRole("textbox", { name: "Service name" }), { target: { value: "Local test service" } });
  fireEvent.click(within(configuration).getByRole("button", { name: "Apply to preview" }));
  expect(within(configuration).getByRole("alert").textContent).toBe("Enter an example server address.");
  for (const endpoint of ["not-an-address", "file:///tmp/example", "https://example:example@mcp.example.invalid/service"]) {
    fireEvent.change(within(configuration).getByRole("textbox", { name: "Server address" }), { target: { value: endpoint } });
    fireEvent.click(within(configuration).getByRole("button", { name: "Apply to preview" }));
    expect(within(configuration).getByRole("alert").textContent).toBe("Use an HTTP(S) example address without credentials.");
  }
  fireEvent.change(within(configuration).getByRole("textbox", { name: "Server address" }), { target: { value: "https://mcp.example.invalid/new" } });
  fireEvent.click(within(configuration).getByRole("button", { name: "Apply to preview" }));
  await finishClosing("Add example MCP service");
  const reopened = await openExample("Local test service");
  fireEvent.click(within(reopened).getByRole("tab", { name: /^Tools/ }));
  expect(within(reopened).getByText("No example tools")).toBeTruthy();
  fireEvent.click(within(reopened).getByRole("tab", { name: "Connection settings" }));
  expect(within(reopened).getByText("Connection not tested")).toBeTruthy();
});

it("preserves edits on both MCP tabs and reveals the tab containing an invalid field", async () => {
  render(<Harness kind="mcp" />);
  enterPreview();
  const configuration = await openExample("Document service");
  fireEvent.change(within(configuration).getByRole("textbox", { name: "Service name" }), { target: { value: "Cross-tab service" } });
  fireEvent.click(within(configuration).getByRole("tab", { name: "Connection settings" }));
  fireEvent.change(within(configuration).getByRole("textbox", { name: "Server address" }), { target: { value: "https://mcp.example.invalid/changed" } });
  fireEvent.click(within(configuration).getByRole("tab", { name: "Basic configuration" }));
  expect((within(configuration).getByRole("textbox", { name: "Service name" }) as HTMLInputElement).value).toBe("Cross-tab service");
  fireEvent.change(within(configuration).getByRole("textbox", { name: "Service name" }), { target: { value: "" } });
  fireEvent.click(within(configuration).getByRole("tab", { name: "Connection settings" }));
  expect((within(configuration).getByRole("textbox", { name: "Server address" }) as HTMLInputElement).value).toBe("https://mcp.example.invalid/changed");
  fireEvent.click(within(configuration).getByRole("button", { name: "Apply to preview" }));
  const name = within(configuration).getByRole("textbox", { name: "Service name" });
  await waitFor(() => expect(document.activeElement).toBe(name));
  expect(within(configuration).getByRole("tab", { name: "Basic configuration" }).getAttribute("aria-selected")).toBe("true");
  fireEvent.change(name, { target: { value: "Cross-tab service" } });
  fireEvent.click(within(configuration).getByRole("tab", { name: "Connection settings" }));
  fireEvent.change(within(configuration).getByRole("textbox", { name: "Server address" }), { target: { value: "" } });
  fireEvent.click(within(configuration).getByRole("tab", { name: "Basic configuration" }));
  fireEvent.click(within(configuration).getByRole("button", { name: "Apply to preview" }));
  expect(within(configuration).getByRole("tab", { name: "Connection settings" }).getAttribute("aria-selected")).toBe("true");
  expect(within(configuration).getByRole("alert").textContent).toBe("Enter an example server address.");
  fireEvent.change(within(configuration).getByRole("textbox", { name: "Server address" }), { target: { value: "https://mcp.example.invalid/changed" } });
  fireEvent.click(within(configuration).getByRole("button", { name: "Apply to preview" }));
  await finishClosing("Document service");
  const reopened = await openExample("Cross-tab service");
  fireEvent.click(within(reopened).getByRole("tab", { name: "Connection settings" }));
  expect((within(reopened).getByRole("textbox", { name: "Server address" }) as HTMLInputElement).value).toBe("https://mcp.example.invalid/changed");
});

it.each(["skills", "mcp"] as const)("provides the %s section through its named list component", (kind) => {
  render(kind === "skills" ? <Skill /> : <Mcp />);
  expect(screen.getByText("Management unavailable")).toBeTruthy();
  enterPreview();
  expect(within(screen.getByRole("list", { name: kind === "skills" ? "Example skills" : "Example MCP services" })).getAllByRole("listitem")).toHaveLength(3);
});
