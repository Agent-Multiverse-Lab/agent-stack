import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import i18n from "@/i18n";
import { ChatMessage } from "@/pages/chat/components/ChatMessage";

afterEach(() => { cleanup(); void i18n.changeLanguage("en"); });

it("shows a compact tool status before completion and expands arguments and results", () => {
  const event = { type: "tool_call", tool_call_id: "call-1", name: "calculator", status: "running", args: { a: 1, b: 2 } };
  const { rerender } = render(<ChatMessage message={{ type: "ai", payload: { type: "tool", event } }} />);
  fireEvent.click(screen.getByRole("button", { name: "calculator In progress" }));
  expect(screen.getByText('"a": 1', { exact: false })).toBeTruthy();
  rerender(<ChatMessage message={{ type: "ai", payload: { type: "tool", event: {
    ...event, status: "completed", output: { content: "3", status: "success" },
  } } }} />);
  expect(screen.getByRole("button", { name: "calculator Completed" })).toBeTruthy();
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
  fireEvent.click(screen.getByRole("button", { name: "execute Failed" }));
  expect(screen.getByText("Command failed")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Reasoning Then calculate." }));
  expect(screen.getByText("First, inspect the inputs.", { exact: false })).toBeTruthy();
});
