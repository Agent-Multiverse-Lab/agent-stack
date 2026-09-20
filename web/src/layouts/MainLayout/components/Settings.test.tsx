import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import i18n from "@/i18n";
import { Settings } from "@/layouts/MainLayout/components/Settings";
import { installBrowserStubs } from "@/test/browserStubs";

afterEach(() => {
  cleanup();
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
