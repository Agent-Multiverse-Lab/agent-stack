import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { SettingsModelOption } from "./SettingsModelOption";

afterEach(cleanup);

it("provides a named checkbox and a selected container", () => {
  const onSelectedChange = vi.fn();
  render(
    <SettingsModelOption
      model={{ model_id: "org/model:latest", capabilities: ["chat"] }}
      isSelected
      onSelectedChange={onSelectedChange}
    />,
  );

  const checkbox = screen.getByRole("checkbox", { name: "org/model:latest" });
  expect(checkbox.getAttribute("aria-checked")).toBe("true");
  expect(screen.getByRole("listitem", { name: "org/model:latest" }).getAttribute("data-selected")).toBe("true");
  fireEvent.click(checkbox);
  expect(onSelectedChange).toHaveBeenCalledWith(false);
});

it("prevents selecting a disabled option while retaining its capability labels", () => {
  const onSelectedChange = vi.fn();
  render(
    <SettingsModelOption
      model={{ model_id: "disabled-model", capabilities: ["tools", "code"] }}
      isDisabled
      onSelectedChange={onSelectedChange}
    />,
  );

  const option = screen.getByRole("listitem", { name: "disabled-model" });
  const checkbox = screen.getByRole("checkbox", { name: "disabled-model" });
  expect(option.getAttribute("aria-disabled")).toBe("true");
  expect(checkbox.getAttribute("aria-disabled")).toBe("true");
  expect(screen.getByText("Tools")).toBeTruthy();
  expect(screen.getByText("Code")).toBeTruthy();
  fireEvent.click(checkbox);
  expect(onSelectedChange).not.toHaveBeenCalled();
});

it("does not introduce selection controls for a configured model", () => {
  render(<SettingsModelOption model={{ model_id: "configured-model", capabilities: [] }} />);

  expect(screen.queryByRole("checkbox")).toBeNull();
  expect(screen.getByRole("listitem", { name: "configured-model" })).toBeTruthy();
  expect(screen.getByText("Capabilities not provided")).toBeTruthy();
});
