import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { Thinking } from "./Thinking";

vi.mock("@/i18n", () => ({
  useTranslation: () => ({ t: (value: string) => value }),
}));

afterEach(cleanup);

it("renders Atom icon and text shimmer when active", () => {
  const { container } = render(<Thinking active={true} label="Thinking" />);
  expect(screen.getByRole("status").textContent).toBe("Thinking");
  const atomIcon = container.querySelector(".lucide-atom");
  expect(atomIcon).toBeTruthy();
  expect(atomIcon?.getAttribute("class")).toContain("motion-safe:animate-spin");
  const shimmerText = container.querySelector(".thinking-shimmer");
  expect(shimmerText).toBeTruthy();
});

it("stops atom spin and shimmer when not active", () => {
  const { container } = render(<Thinking active={false} label="Execution process" />);
  expect(screen.queryByRole("status")).toBeNull();
  expect(screen.getByText("Execution process")).toBeTruthy();
  const atomIcon = container.querySelector(".lucide-atom");
  expect(atomIcon).toBeTruthy();
  expect(atomIcon?.getAttribute("class")).not.toContain("motion-safe:animate-spin");
  expect(container.querySelector(".thinking-shimmer")).toBeNull();
});

it("expands and collapses children details on demand", () => {
  render(
    <Thinking active={false} label="Execution process">
      <div>Child Content</div>
    </Thinking>
  );
  expect(screen.queryByText("Child Content")).toBeNull();
  const trigger = screen.getByRole("button", { name: "Expand thinking details" });
  fireEvent.click(trigger);
  expect(screen.getByText("Child Content")).toBeTruthy();
});
