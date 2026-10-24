import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ConversationMessages } from "./ConversationMessages";
import type { ChatMessage } from "@/pages/chat/types";

afterEach(cleanup);
const startedAt = Date.parse("2026-10-24T10:00:00Z");
const props = {
  threadId: "thread", currentRunId: "run", status: "running", active: true,
  waiting: false, startedAt,
};
function text(content: string, threadId = "thread"): ChatMessage {
  return { type: "ai", payload: { type: "text", event: {
    content, run_id: "run", thread_id: threadId,
    run: { run_id: "run", status: "completed", started_at: new Date(startedAt).toISOString(), finished_at: new Date(startedAt + 5000).toISOString() },
  } } };
}
const reasoning: ChatMessage = { type: "ai", payload: { type: "tool", event: {
  type: "reasoning", content: "Check the sources", run_id: "run", thread_id: "thread",
} } };

it("keeps the live indicator after text arrives and separates the final answer from collapsed work", () => {
  const messages = [text("I will check the sources"), reasoning, text("The answer is 42")];
  const view = render(<ConversationMessages {...props} messages={messages} />);
  expect(screen.getByRole("status")).toBeTruthy();
  expect(screen.getByText("I will check the sources")).toBeTruthy();
  expect(screen.getByText("The answer is 42")).toBeTruthy();
  view.rerender(<ConversationMessages {...props} active={false} status="completed" messages={messages} />);
  expect(screen.queryByRole("status")).toBeNull();
  expect(screen.queryByText("I will check the sources")).toBeNull();
  expect(screen.getByText("The answer is 42")).toBeTruthy();
  expect(screen.getByText("5.0s")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /Expand thinking details|展开思考/ }));
  expect(screen.getByText("I will check the sources")).toBeTruthy();
});

it("keeps child-agent output inside the process", () => {
  render(<ConversationMessages {...props} active={false} status="completed" messages={[reasoning, text("Child result", "child")]} />);
  expect(screen.queryByText("Child result")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Expand thinking details|展开思考/ }));
  expect(screen.getByText("Child result")).toBeTruthy();
});

it("does not create an empty process group for a completed plain answer", () => {
  render(<ConversationMessages {...props} active={false} status="completed" messages={[text("Plain answer")]} />);
  expect(screen.getByText("Plain answer")).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
});

it("stops the live indicator while waiting for user input", () => {
  render(<ConversationMessages {...props} waiting messages={[reasoning]} />);
  expect(screen.queryByRole("status")).toBeNull();
  expect(screen.getByText(/Waiting for your response|等待你的操作/)).toBeTruthy();
});

it("groups persisted messages by their nested run metadata", () => {
  const persisted = (content: string): ChatMessage => ({ type: "ai", payload: {
    type: "text", event: { content, run: { run_id: "old", status: "completed",
      started_at: new Date(startedAt).toISOString(), finished_at: new Date(startedAt + 3000).toISOString() } },
  } });
  render(<ConversationMessages {...props} active={false} currentRunId={null}
    messages={[persisted("Earlier explanation"), persisted("Saved answer")]} />);
  expect(screen.getByText("Saved answer")).toBeTruthy();
  expect(screen.queryByText("Earlier explanation")).toBeNull();
  expect(screen.getByText("3.0s")).toBeTruthy();
});
