import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ThemeProvider } from "next-themes";

import i18n from "@/i18n";
import { Settings } from "@/layouts/MainLayout/components/Settings";
import { installBrowserStubs } from "@/test/browserStubs";

vi.mock("@/layouts/MainLayout/components/SettingsModels", () => ({
  default: () => <div>Model connection settings</div>,
}));

afterEach(() => {
  cleanup();
  document.documentElement.classList.remove("dark", "light");
  window.localStorage.removeItem("am-theme");
  act(() => {
    void i18n.changeLanguage("en");
  });
  vi.unstubAllGlobals();
});

it("switches the application language from Settings and persists the choice", async () => {
  installBrowserStubs();
  render(<Settings open close={() => {}} user={null} />);

  expect(within(screen.getByRole("combobox", { name: "Language" })).getByText("English")).toBeTruthy();
  fireEvent.click(screen.getByRole("combobox", { name: "Language" }));
  const chinese = await screen.findByRole("option", { name: "简体中文" });
  fireEvent.keyDown(chinese, { key: "Enter", code: "Enter" });

  expect(screen.getByRole("dialog", { name: "设置" })).toBeTruthy();
  expect(within(screen.getByRole("combobox", { name: "语言" })).getByText("简体中文")).toBeTruthy();
  expect(within(screen.getByRole("combobox", { name: "主题" })).getByText("浅色")).toBeTruthy();
  expect(document.documentElement.lang).toBe("zh-CN");
  expect(window.localStorage.getItem("am-language")).toBe("zh-CN");
});

it("shows the approved Settings sections without unrelated controls", () => {
  installBrowserStubs();
  render(<Settings open close={() => {}} user={null} />);

  const navigation = within(screen.getByLabelText("Settings sections"));
  expect(navigation.getAllByRole("button").map((button) => button.textContent))
    .toEqual(["General", "Account", "Models", "Skills", "MCP"]);
  expect(screen.getByRole("combobox", { name: "Theme" })).toBeTruthy();
  expect(screen.getByRole("combobox", { name: "Language" })).toBeTruthy();
  expect(screen.queryByRole("switch")).toBeNull();
  for (const label of [
    "Data Controls",
    "About",
    "Show follow-up suggestions",
    "Improve the model",
    "Product",
    "Version",
    "Preview",
  ]) {
    expect(screen.queryByText(label)).toBeNull();
  }
});

it("uses sidebar navigation and preserves the signed-out account state", () => {
  installBrowserStubs();
  render(<Settings open close={() => {}} user={null} />);

  fireEvent.click(screen.getByRole("button", { name: "Account" }));

  expect(screen.getByRole("heading", { name: "Account" })).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "Account" }).hasAttribute("data-active"),
  ).toBe(true);
  expect(screen.getByText("Not logged in")).toBeTruthy();
  expect(screen.getByText("—")).toBeTruthy();
});

it.each([true, false])("displays the real account email and is_active=%s", (isActive) => {
  installBrowserStubs();
  render(<Settings open close={() => {}} user={{
    id: 1,
    uid: "user-1",
    email: "user@example.com",
    is_active: isActive,
    is_admin: false,
  }} />);

  fireEvent.click(screen.getByRole("button", { name: "Account" }));

  expect(screen.getByText("user@example.com")).toBeTruthy();
  expect(screen.getByText(isActive ? "Active" : "Inactive")).toBeTruthy();
  expect(screen.queryByText("Not logged in")).toBeNull();
});

it.each(["Account", "Models", "Skills", "MCP"])("reopens General after closing %s", async (section) => {
  installBrowserStubs();
  const close = vi.fn();
  const { rerender } = render(<Settings open close={close} user={null} />);

  fireEvent.click(screen.getByRole("button", { name: section }));
  expect(screen.getByRole("heading", { name: section })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(close).toHaveBeenCalledOnce();
  rerender(<Settings open={false} close={close} user={null} />);
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

  rerender(<Settings open close={close} user={null} />);

  expect(screen.getByRole("heading", { name: "General" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "General" }).hasAttribute("data-active"))
    .toBe(true);
  expect(screen.getByRole("combobox", { name: "Theme" })).toBeTruthy();
  expect(screen.getByRole("combobox", { name: "Language" })).toBeTruthy();
});

it("applies and persists the selected color theme", async () => {
  installBrowserStubs();
  render(
    <ThemeProvider attribute="class" defaultTheme="light" storageKey="am-theme">
      <Settings open close={() => {}} user={null} />
    </ThemeProvider>,
  );

  expect(within(screen.getByRole("combobox", { name: "Theme" })).getByText("Light")).toBeTruthy();
  fireEvent.click(screen.getByRole("combobox", { name: "Theme" }));
  const dark = await screen.findByRole("option", { name: "Dark" });
  fireEvent.keyDown(dark, { key: "Enter", code: "Enter" });

  await waitFor(() => expect(document.documentElement.classList.contains("dark")).toBe(true));
  expect(window.localStorage.getItem("am-theme")).toBe("dark");
  expect(within(screen.getByRole("combobox", { name: "Theme" })).getByText("Dark")).toBeTruthy();

  fireEvent.click(screen.getByRole("combobox", { name: "Theme" }));
  const light = await screen.findByRole("option", { name: "Light" });
  fireEvent.keyDown(light, { key: "Enter", code: "Enter" });

  await waitFor(() => expect(document.documentElement.classList.contains("dark")).toBe(false));
  expect(window.localStorage.getItem("am-theme")).toBe("light");
  expect(within(screen.getByRole("combobox", { name: "Theme" })).getByText("Light")).toBeTruthy();

  fireEvent.click(screen.getByRole("combobox", { name: "Theme" }));
  const system = await screen.findByRole("option", { name: "System" });
  fireEvent.keyDown(system, { key: "Enter", code: "Enter" });

  expect(window.localStorage.getItem("am-theme")).toBe("system");
  expect(within(screen.getByRole("combobox", { name: "Theme" })).getByText("System")).toBeTruthy();
});

it.each([false, true])("opens model management with is_admin=%s", (isAdmin) => {
  installBrowserStubs();
  const user = {
    id: 1,
    uid: "user-1",
    email: "user@example.com",
    is_active: true,
    is_admin: isAdmin,
  };
  render(<Settings open close={() => {}} user={user} />);

  fireEvent.click(screen.getByRole("button", { name: "Models" }));

  expect(screen.getByRole("heading", { name: "Models" })).toBeTruthy();
  expect(screen.getByText("Model connection settings")).toBeTruthy();
});
