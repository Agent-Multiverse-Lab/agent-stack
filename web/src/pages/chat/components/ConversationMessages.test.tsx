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

it("stops the live indicator once final answer arrives and separates answer from collapsed work", () => {
  const workingMessages = [text("I will check the sources"), reasoning];
  const view = render(<ConversationMessages {...props} messages={workingMessages} />);
  expect(screen.getByRole("status")).toBeTruthy();
  expect(screen.getByText("I will check the sources")).toBeTruthy();

  const finishedMessages = [...workingMessages, text("The answer is 42")];
  view.rerender(<ConversationMessages {...props} messages={finishedMessages} />);
  // Once the answer arrives, the thinking/working live status is stopped
  expect(screen.queryByRole("status")).toBeNull();
  expect(screen.getByText("The answer is 42")).toBeTruthy();
  // Work is collapsed under Execution process
  expect(screen.queryByText("I will check the sources")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Expand thinking details|展开思考/ }));
  expect(screen.getByText("I will check the sources")).toBeTruthy();
});

it("does not show thinking or empty process when an answer arrives even while run is active", () => {
  render(<ConversationMessages {...props} active={true} messages={[text("Plain answer")]} />);
  expect(screen.getByText("Plain answer")).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
  expect(screen.queryByRole("status")).toBeNull();
  expect(screen.queryByText(/Thinking|思考中/)).toBeNull();
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

it("records thinking duration up until answer output, ignoring full run finished_at duration", () => {
  const answerCreatedAt = new Date(startedAt + 1200).toISOString();
  const runFinishedAt = new Date(startedAt + 30_000).toISOString();
  const answerWithTimestamp: ChatMessage = {
    type: "ai",
    payload: {
      type: "text",
      event: {
        content: "Done answer",
        created_at: answerCreatedAt,
        run_id: "run",
        thread_id: "thread",
        run: {
          run_id: "run",
          status: "completed",
          started_at: new Date(startedAt).toISOString(),
          finished_at: runFinishedAt,
        },
      },
    },
  };
  render(
    <ConversationMessages
      {...props}
      active={false}
      currentRunId={null}
      messages={[reasoning, answerWithTimestamp]}
    />,
  );
  expect(screen.getByText("Done answer")).toBeTruthy();
  // Duration should be 1.2s (until answer output), not 30.0s (whole agent execution cycle)
  expect(screen.getByText("1.2s")).toBeTruthy();
  expect(screen.queryByText("30.0s")).toBeNull();
});
