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
function toolCall(
  toolCallId: string,
  name: string,
  status: string,
  args: Record<string, unknown> = {},
  output?: unknown,
): ChatMessage {
  return {
    type: "ai",
    payload: {
      type: "tool",
      event: {
        type: "tool_call",
        tool_call_id: toolCallId,
        name,
        status,
        args,
        output,
        run_id: "run",
        thread_id: "thread",
      },
    },
  };
}
const reasoning: ChatMessage = { type: "ai", payload: { type: "tool", event: {
  type: "reasoning", content: "Check the sources", run_id: "run", thread_id: "thread",
} } };

it("keeps expanded tool details mounted between narration and the next tool call", () => {
  const messages = [toolCall("search-1", "web_search", "completed", { query: "latest" }, "Search results")];
  const view = render(<ConversationMessages {...props} messages={messages} />);
  const searchButton = screen.getByRole("button", { name: /Search the web|网络搜索/ });
  fireEvent.click(searchButton);
  expect(screen.getByText("Search results")).toBeTruthy();

  view.rerender(<ConversationMessages {...props} messages={[...messages, text("I will verify these results")]} />);
  expect(screen.getByRole("button", { name: /Search the web|网络搜索/ })).toBe(searchButton);
  expect(screen.getByText("Search results")).toBeTruthy();

  view.rerender(<ConversationMessages {...props} messages={[
    ...messages, text("I will verify these results"),
    toolCall("search-2", "read_file", "running"),
  ]} />);
  expect(screen.getByRole("button", { name: /Search the web|网络搜索/ })).toBe(searchButton);
  expect(screen.getByText("Search results")).toBeTruthy();
});

it("summarizes multiple tools with their names and live status", () => {
  render(<ConversationMessages {...props} messages={[
    toolCall("search-1", "web_search", "completed"),
    toolCall("read-1", "read_file", "running"),
  ]} />);

  expect(screen.getByText(/Called 2 tools|已调用 2 个工具/)).toBeTruthy();
  expect(screen.getByText(/Search the web.*Read file|搜索网页.*读取文件/)).toBeTruthy();
  expect(screen.getByText(/1 in progress|1 进行中/)).toBeTruthy();
});

it("keeps only the final main-thread text outside the execution process", () => {
  const step1Messages = [
    text("I will check the sources"),
    reasoning,
    toolCall("call-1", "knowledge_search", "running", { query: "agent" }),
    toolCall("call-2", "read_file", "pending", { path: "README.md" }),
  ];
  const view = render(<ConversationMessages {...props} messages={step1Messages} />);

  // While a later process event exists, the earlier text belongs to the process.
  expect(screen.getByText("I will check the sources")).toBeTruthy();
  // Process Thinking container is active and expanded while tools are running
  expect(screen.getByRole("status").textContent).toMatch(
    /Reasoning and tool calls.*2 tools|推理与工具调用.*2 个工具/,
  );
  expect(screen.getByRole("button", { name: /Search knowledge base|检索知识库/ })).toBeTruthy();
  expect(screen.getByRole("button", { name: /Read file|读取文件/ })).toBeTruthy();

  const finishedMessages = [
    text("I will check the sources"),
    reasoning,
    toolCall("call-1", "knowledge_search", "completed", { query: "agent" }, "doc-1"),
    toolCall("call-2", "read_file", "completed", { path: "README.md" }, "file-content"),
    text("The answer is 42"),
  ];
  view.rerender(<ConversationMessages {...props} active={false} status="completed" messages={finishedMessages} />);

  // Live indicator stops once run completes
  expect(screen.queryByRole("status")).toBeNull();
  // The final main-thread text is the only text outside the collapsed process.
  expect(screen.queryByText("I will check the sources")).toBeNull();
  expect(screen.getByText("The answer is 42")).toBeTruthy();

  // Process Thinking container is collapsed with its real tool summary.
  expect(screen.getByText(/Reasoning and tool calls.*2 tools|推理与工具调用.*2 个工具/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Search knowledge base|检索知识库/ })).toBeNull();

  // Expanding Thinking reveals reasoning, tools, and their arguments/outputs
  fireEvent.click(screen.getByRole("button", { name: /Expand thinking details|展开思考/ }));
  expect(screen.getByText("I will check the sources")).toBeTruthy();
  expect(screen.getByText("Check the sources")).toBeTruthy();
  const searchToolBtn = screen.getByRole("button", { name: /Search knowledge base|检索知识库/ });
  expect(searchToolBtn).toBeTruthy();
  fireEvent.click(searchToolBtn);
  expect(screen.getByText(/"query": "agent"/)).toBeTruthy();
  expect(screen.getByText("doc-1")).toBeTruthy();
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

it("renders only the persisted final answer outside and keeps earlier text with tools", () => {
  const persistedText = (content: string): ChatMessage => ({ type: "ai", payload: {
    type: "text", event: { content, run: { run_id: "old", status: "completed",
      started_at: new Date(startedAt).toISOString(), finished_at: new Date(startedAt + 3000).toISOString() } },
  } });
  const persistedTool: ChatMessage = {
    type: "ai",
    payload: {
      type: "tool",
      event: {
        type: "tool_call",
        tool_call_id: "db-tool-1",
        name: "calculator",
        status: "completed",
        args: { expression: "6 * 7" },
        output: "42",
        run: {
          run_id: "old",
          status: "completed",
          started_at: new Date(startedAt).toISOString(),
          finished_at: new Date(startedAt + 3000).toISOString(),
        },
      },
    },
  };
  render(<ConversationMessages {...props} active={false} currentRunId={null}
    messages={[persistedText("Earlier explanation"), persistedTool, persistedText("Saved answer")]} />);
  expect(screen.queryByText("Earlier explanation")).toBeNull();
  expect(screen.getByText("Saved answer")).toBeTruthy();
  expect(screen.getByText(/Calling: Calculate|调用：计算/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /Expand thinking details|展开思考/ }));
  expect(screen.getByText("Earlier explanation")).toBeTruthy();
});

it("moves a provisional answer back into the process when a later tool event arrives", () => {
  const view = render(
    <ConversationMessages {...props} messages={[text("Provisional answer")]} />,
  );
  expect(screen.getByText("Provisional answer")).toBeTruthy();
  expect(screen.queryByRole("status")).toBeNull();

  view.rerender(
    <ConversationMessages
      {...props}
      messages={[
        text("Provisional answer"),
        toolCall("call-later", "web_search", "running", { query: "latest" }),
      ]}
    />,
  );

  expect(screen.getByRole("status")).toBeTruthy();
  expect(screen.getByText("Provisional answer")).toBeTruthy();
  expect(screen.getByRole("button", { name: /Search the web|网络搜索/ })).toBeTruthy();
});

it("stops live indicator when answer arrives even if full run has later finished_at", () => {
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
  expect(screen.queryByRole("status")).toBeNull();
  expect(screen.getByText(/Execution process|执行过程/)).toBeTruthy();
});
