import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import qwenIcon from "@/assets/models/qwen-color.svg";

import ModelSelector from "@/pages/chat/components/ModelSelector";
import { installBrowserStubs } from "@/test/browserStubs";

afterEach(cleanup);

it.each(["", "qwen-model"])("closes after selecting a model with current selection %s", async (selectedId) => {
  installBrowserStubs();
  const select = vi.fn();
  render(
    <ModelSelector
      models={[{
        id: "qwen-model",
        name: "qwen-3.5-plus",
        display_name: "Qwen",
        version: "1",
        provider: "qwen",
        icon: "qwen",
        is_available: true,
        is_default: true,
        is_fallback: false,
        is_flash: false,
      }]}
      selectedId={selectedId}
      loading={false}
      disabled={false}
      placement="top"
      select={select}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Select model" }));
  const option = screen.getByRole("menuitemradio", { name: "qwen-3.5-plus" });
  expect(option.querySelector("img")?.getAttribute("src")).toBe(qwenIcon);
  fireEvent.pointerEnter(option);
  expect(document.querySelector("[data-model-highlight]")).toBeTruthy();

  fireEvent.click(option);
  if (!selectedId) expect(select).toHaveBeenCalledWith("qwen-model");
  await waitFor(() => expect(screen.queryByRole("menuitemradio")).toBeNull());
  expect(screen.getByRole("button", { name: "Select model" }).getAttribute("aria-expanded")).toBe("false");
});
