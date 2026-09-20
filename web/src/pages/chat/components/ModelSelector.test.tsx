import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import ModelSelector from "@/pages/chat/components/ModelSelector";
import { installBrowserStubs } from "@/test/browserStubs";

it("selects a model directly from the shadcn menu", () => {
  installBrowserStubs();
  const select = vi.fn();
  render(
    <ModelSelector
      models={[{
        id: "qwen-model",
        name: "Qwen Model",
        display_name: "Qwen Model",
        version: "1",
        provider: "qwen",
        icon: "qwen",
        is_available: true,
        is_default: true,
        is_fallback: false,
        is_flash: false,
      }]}
      selectedId=""
      loading={false}
      disabled={false}
      placement="top"
      select={select}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Select model" }));
  const option = screen.getByRole("menuitemradio", { name: /Qwen Model/ });
  fireEvent.pointerEnter(option);
  expect(document.querySelector("[data-model-highlight]")).toBeTruthy();

  fireEvent.click(option);
  expect(select).toHaveBeenCalledWith("qwen-model");
});
