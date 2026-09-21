import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

import SandboxPage from "@/pages/sandbox/SandboxPage";
import { installBrowserStubs } from "@/test/browserStubs";

afterEach(cleanup);

it("opens a workspace folder from the file list", () => {
  installBrowserStubs();
  render(<SandboxPage />);

  const outputsButtons = screen.getAllByRole("button", { name: "outputs" });
  fireEvent.click(outputsButtons.at(-1)!);

  expect(screen.getByText("analysis-report.md")).toBeTruthy();
  expect(screen.getByText("scene-summary.json")).toBeTruthy();
});

it("filters entries in the current folder", () => {
  installBrowserStubs();
  render(<SandboxPage />);

  fireEvent.change(screen.getAllByRole("textbox", { name: "Filter this folder" })[0], {
    target: { value: "readme" },
  });

  const fileTable = within(screen.getByRole("table"));
  expect(fileTable.getByText("README.md")).toBeTruthy();
  expect(fileTable.queryByText("scripts")).toBeNull();
});
