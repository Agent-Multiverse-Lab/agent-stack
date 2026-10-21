import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import i18n from "@/i18n";
import { ChatMessage } from "@/pages/chat/components/ChatMessage";

afterEach(() => { cleanup(); void i18n.changeLanguage("en"); });

it("shows a compact tool status before completion and expands arguments and results", () => {
  const event = { type: "tool_call", tool_call_id: "call-1", name: "calculator", status: "running", args: { a: 1, b: 2 } };
  const { rerender } = render(<ChatMessage message={{ type: "ai", payload: { type: "tool", event } }} />);
  const running = screen.getByRole("button", { name: "calculator In progress" });
  expect(running.querySelector('[data-tool-status-icon="running"] svg')?.getAttribute("class"))
    .toContain("motion-safe:animate-spin");
  fireEvent.click(running);
  expect(screen.getByText('"a": 1', { exact: false })).toBeTruthy();
  rerender(<ChatMessage message={{ type: "ai", payload: { type: "tool", event: {
    ...event, status: "completed", output: { content: "3", status: "success" },
  } } }} />);
  const completed = screen.getByRole("button", { name: "calculator Completed" });
  expect(completed.querySelector('[data-tool-status-icon="completed"] svg')?.getAttribute("class"))
    .toContain("motion-safe:zoom-in-75");
  expect(screen.getByText("3", { exact: true })).toBeTruthy();
  expect(screen.queryByText('"status": "success"', { exact: false })).toBeNull();
});

it("renders tool errors and keeps reasoning in a separate expandable block", () => {
  render(<>
    <ChatMessage message={{ type: "ai", payload: { type: "tool", event: {
      type: "tool_call", name: "execute", status: "error", error: "Command failed",
    } } }} />
    <ChatMessage message={{ type: "ai", payload: { type: "tool", event: {
      type: "reasoning", content: "First, inspect the inputs.\nThen calculate.",
    } } }} />
  </>);
  const failed = screen.getByRole("button", { name: "execute Failed" });
  expect(failed.querySelector('[data-tool-status-icon="error"] svg')?.getAttribute("class"))
    .toContain("motion-safe:spin-in-12");
  fireEvent.click(failed);
  expect(screen.getByText("Command failed")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Reasoning Then calculate." }));
  expect(screen.getByText("First, inspect the inputs.", { exact: false })).toBeTruthy();
});

it("falls back safely when the backend sends an unknown status", () => {
  render(<ChatMessage message={{ type: "ai", payload: { type: "tool", event: {
    type: "tool_call", name: "search", status: "constructor",
  } } }} />);

  expect(screen.getByRole("button", { name: "search Pending" })).toBeTruthy();
});
