import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import i18n from "@/i18n";
import { ChatMessage } from "@/pages/chat/components/ChatMessage";

afterEach(() => { cleanup(); void i18n.changeLanguage("en"); });

it("shows a compact tool status before completion and expands arguments and results", () => {
  const event = { type: "tool_call", tool_call_id: "call-1", name: "calculator", status: "running", args: { a: 1, b: 2 } };
  const { rerender } = render(<ChatMessage message={{ type: "ai", payload: { type: "tool", event } }} />);
  const running = screen.getByRole("button", { name: "calculator In progress" });
  const runningSvg = running.querySelector('[data-tool-status-icon="running"] svg');
  expect(runningSvg?.getAttribute("class")).toContain("motion-safe:animate-spin");
  expect(runningSvg?.getAttribute("class")).toContain("size-6");
  expect(runningSvg?.getAttribute("viewBox")).toBe("0 0 24 24");
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
  expect(failed.querySelector('[data-tool-status-icon="error"] svg')).toBeTruthy();
  expect(failed.querySelectorAll("svg").length).toBe(2);
  fireEvent.click(failed);
  expect(screen.getByText("Command failed")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Reasoning Then calculate." }));
  expect(screen.getByText("First, inspect the inputs.", { exact: false })).toBeTruthy();
});

it("falls back safely when the backend sends an unknown status", () => {
  render(<ChatMessage message={{ type: "ai", payload: { type: "tool", event: {
    type: "tool_call", name: "search", status: "constructor",
  } } }} />);

  const fallback = screen.getByRole("button", { name: "search In progress" });
  expect(fallback.querySelector('[data-tool-status-icon="pending"] svg')?.getAttribute("class"))
    .toContain("motion-safe:animate-spin");
});

it("renders agent tasks in a bordered container with status transitions", () => {
  const { rerender } = render(
    <ChatMessage
      message={{
        type: "ai",
        payload: {
          type: "tool",
          event: {
            name: "agent_state",
            agent_state: {
              agent_todo: [
                { content: "Analyze query", status: "in_progress" },
                { content: "Write report", status: "pending" },
              ],
            },
          },
        },
      }}
    />,
  );

  expect(document.querySelector('[data-task-group-status="running"]')).toBeTruthy();
  expect(document.querySelector('[data-task-status="in_progress"]')).toBeTruthy();
  expect(document.querySelector('[data-task-status="pending"]')).toBeTruthy();

  rerender(
    <ChatMessage
      message={{
        type: "ai",
        payload: {
          type: "tool",
          event: {
            name: "agent_state",
            agent_state: {
              agent_todo: [
                { content: "Analyze query", status: "completed" },
                { content: "Write report", status: "completed" },
              ],
            },
          },
        },
      }}
    />,
  );

  expect(document.querySelector('[data-task-group-status="completed"]')).toBeTruthy();
  expect(document.querySelectorAll('[data-task-status="completed"]').length).toBe(2);
});
