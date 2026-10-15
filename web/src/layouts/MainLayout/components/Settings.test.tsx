import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

  fireEvent.click(screen.getByRole("combobox", { name: "Language" }));
  const chinese = await screen.findByRole("option", { name: "简体中文" });
  fireEvent.keyDown(chinese, { key: "Enter", code: "Enter" });

  expect(screen.getByRole("dialog", { name: "设置" })).toBeTruthy();
  expect(screen.getByRole("combobox", { name: "语言" })).toBeTruthy();
  expect(document.documentElement.lang).toBe("zh-CN");
  expect(window.localStorage.getItem("am-language")).toBe("zh-CN");
});

it("uses sidebar navigation for Settings sections", () => {
  installBrowserStubs();
  render(<Settings open close={() => {}} user={null} />);

  fireEvent.click(screen.getByRole("button", { name: "Account" }));

  expect(screen.getByRole("heading", { name: "Account" })).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "Account" }).hasAttribute("data-active"),
  ).toBe(true);
});

it("applies and persists the selected color theme", async () => {
  installBrowserStubs();
  render(
    <ThemeProvider attribute="class" defaultTheme="light" storageKey="am-theme">
      <Settings open close={() => {}} user={null} />
    </ThemeProvider>,
  );

  fireEvent.click(screen.getByRole("combobox", { name: "Theme" }));
  const dark = await screen.findByRole("option", { name: "Dark" });
  fireEvent.keyDown(dark, { key: "Enter", code: "Enter" });

  await waitFor(() => expect(document.documentElement.classList.contains("dark")).toBe(true));
  expect(window.localStorage.getItem("am-theme")).toBe("dark");

  fireEvent.click(screen.getByRole("combobox", { name: "Theme" }));
  const light = await screen.findByRole("option", { name: "Light" });
  fireEvent.keyDown(light, { key: "Enter", code: "Enter" });

  await waitFor(() => expect(document.documentElement.classList.contains("dark")).toBe(false));
  expect(window.localStorage.getItem("am-theme")).toBe("light");
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
