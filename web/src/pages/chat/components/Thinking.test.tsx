import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";

import { Thinking } from "./Thinking";

vi.mock("@/i18n", () => ({
  useTranslation: () => ({ t: (value: string) => value }),
}));

const startedAt = Date.parse("2026-10-18T00:00:00Z");

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
  vi.setSystemTime(startedAt + 12_300);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

it("shows the run elapsed time immediately and includes time spent unmounted", () => {
  const view = render(<Thinking startedAt={startedAt} />);
  expect(screen.getByText("12.3s")).toBeTruthy();
  act(() => vi.advanceTimersByTime(700));
  expect(screen.getByText("13.0s")).toBeTruthy();
  view.rerender(<div />);
  expect(vi.getTimerCount()).toBe(0);
  act(() => vi.advanceTimersByTime(5_000));
  view.rerender(<Thinking startedAt={startedAt} />);
  expect(screen.getByText("18.0s")).toBeTruthy();
});

it("waits for a valid start time and hydrates it without a zero-time frame", () => {
  const view = render(<Thinking startedAt={null} />);
  expect(screen.getByRole("status").textContent).toBe("Thinking");
  expect(vi.getTimerCount()).toBe(0);
  view.rerender(<Thinking startedAt={NaN} />);
  expect(screen.getByRole("status").textContent).toBe("Thinking");
  view.rerender(<Thinking startedAt={startedAt} />);
  expect(screen.getByText("12.3s")).toBeTruthy();
  view.rerender(<Thinking startedAt={startedAt - 60_000} />);
  expect(screen.getByText("1m 12.3s")).toBeTruthy();
});

it("clamps a future start time to zero and cleans up its timer", () => {
  const view = render(<Thinking startedAt={startedAt + 20_000} />);
  expect(screen.getByText("0.0s")).toBeTruthy();
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
});

it("renders the 3x3 pixel grid and supports Drive, Dots, Orbit, and Surfer variants", () => {
  const view = render(<Thinking startedAt={startedAt} />);
  const pixels = view.container.querySelectorAll(".thinking-pixel");
  expect(pixels).toHaveLength(9);
  expect((pixels[0] as HTMLElement).style.animation).toContain("pixel-on 650ms ease-in-out 90ms infinite");

  view.rerender(<Thinking variant="Orbit" startedAt={startedAt} />);
  const orbitPixels = view.container.querySelectorAll(".thinking-pixel");
  expect((orbitPixels[4] as HTMLElement).style.animation).toBe("none");
  expect((orbitPixels[4] as HTMLElement).style.opacity).toBe("0.07");

  view.rerender(<Thinking variant="Surfer" startedAt={startedAt} />);
  expect(screen.getByText("Subway surfing")).toBeTruthy();
  expect(view.container.querySelector("video")).toBeTruthy();
});
