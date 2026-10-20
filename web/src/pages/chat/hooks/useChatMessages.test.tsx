import { afterEach, expect, it, vi } from "vitest"
import { act, cleanup, renderHook } from "@testing-library/react"

import { useChatMessages } from "@/pages/chat/hooks/useChatMessages"
import type { AgentRunStreamEvent } from "@/types/chat"

afterEach(() => { cleanup(); vi.useRealTimers() })

it("smooths a burst before flushing the complete text", () => {
  vi.useFakeTimers()
  const { result } = renderHook(() => useChatMessages())
  const content = "a".repeat(200)
  const event: AgentRunStreamEvent = {
    id: "1",
    scope: "agent_run",
    type: "messages",
    run_id: "run-1",
    thread_id: "thread-1",
    created_at: new Date().toISOString(),
    items: [{
      stream_event: [
        { type: "message_delta", message_id: "assistant-1", content_delta: content }
      ]
    }]
  }

  act(() => result.current.applyRunMessageEvent(event, "run-1"))
  expect((result.current.messages[0].payload.event as { content: string }).content).toBe("")

  act(() => vi.advanceTimersByTime(240))
  const partial = (result.current.messages[0].payload.event as { content: string }).content
  expect(partial.length).toBeGreaterThan(0)
  expect(partial.length).toBeLessThan(content.length)

  act(() => result.current.flushStream("thread-1"))
  expect((result.current.messages[0].payload.event as { content: string }).content).toBe(content)
})

const streamEvent = (type: string, fields: Record<string, unknown> = {}): AgentRunStreamEvent => ({
  id: "event-1", scope: "agent_run", type, run_id: "run-1",
  thread_id: "thread-1", created_at: "2026-10-20T00:00:00Z", ...fields,
})

const toolEvent = (event: string, fields: Record<string, unknown> = {}, threadId = "thread-1") =>
  streamEvent("custom", {
    name: "agent_execute_event", thread_id: threadId,
    event: { stream_methods: "tools", stream_namesapce: [], stream_data: {
      event, tool_call_id: "call-1", ...fields,
    } },
  })

it("keeps ask_user out of ordinary tool cards throughout its lifecycle", () => {
  const { result } = renderHook(() => useChatMessages())
  act(() => result.current.applyRunMessageEvent(streamEvent("messages", { items: [{ stream_event: [
    { type: "tool_call", message_id: "assistant-1", tool_call_id: "call-1", name: "ask_user", args: { questions: [] } },
  ] }] }), "run-1"))
  expect(result.current.messages).toHaveLength(0)
  act(() => {
    result.current.applyRunMessageEvent(toolEvent("tool-started", { tool_name: "ask_user" }), "run-1")
    result.current.applyRunMessageEvent(toolEvent("tool-output-delta", { delta: "waiting" }), "run-1")
    result.current.applyRunMessageEvent(toolEvent("tool-error", { message: "GraphInterrupt" }), "run-1")
    result.current.applyRunMessageEvent(toolEvent("tool-finished", { output: { answer: "yes" } }), "run-1")
  })
  expect(result.current.messages).toHaveLength(0)
})

it("removes an unnamed placeholder when ask_user is identified without hiding another thread's tool", () => {
  const { result } = renderHook(() => useChatMessages())
  act(() => result.current.applyRunMessageEvent(streamEvent("messages", { items: [{ stream_event: [
    { type: "tool_call", message_id: "assistant-1", tool_call_id: "call-1", args: {} },
  ] }] }), "run-1"))
  expect(result.current.messages).toHaveLength(1)
  act(() => {
    result.current.applyRunMessageEvent(toolEvent("tool-started", { tool_name: "ask_user" }), "run-1")
    result.current.applyRunMessageEvent(toolEvent("tool-started", { tool_name: "calculator" }, "child-1"), "run-1")
  })
  expect(result.current.messages).toHaveLength(1)
  expect(result.current.messages[0].payload.event).toMatchObject({ name: "calculator", thread_id: "child-1" })
})

it("shows tool execution immediately and merges start, progress and result into one activity", () => {
  const { result } = renderHook(() => useChatMessages())
  act(() => result.current.applyRunMessageEvent(toolEvent("tool-started", {
    tool_name: "calculator", input: { expression: "1 + 2" },
  }), "run-1"))
  expect(result.current.messages).toHaveLength(1)
  expect(result.current.messages[0].payload.event).toMatchObject({
    type: "tool_call", name: "calculator", status: "running", args: { expression: "1 + 2" },
  })
  act(() => {
    result.current.applyRunMessageEvent(toolEvent("tool-output-delta", { delta: "working " }), "run-1")
    result.current.applyRunMessageEvent(toolEvent("tool-output-delta", { delta: "on it" }), "run-1")
    result.current.applyRunMessageEvent(toolEvent("tool-finished", { output: { content: "3", status: "success" } }), "run-1")
  })
  expect(result.current.messages).toHaveLength(1)
  expect(result.current.messages[0].payload.event).toMatchObject({
    name: "calculator", status: "completed", output_deltas: ["working ", "on it"],
    output: { content: "3" },
  })
})

it("merges tool_call messages with their matching execution events", () => {
  const { result } = renderHook(() => useChatMessages())
  act(() => result.current.applyRunMessageEvent(streamEvent("messages", { items: [{ stream_event: [
    { type: "tool_call", message_id: "assistant-1", tool_call_id: "call-1", name: "calculator", args: { a: 1, b: 2 } },
  ] }] }), "run-1"))
  expect(result.current.messages[0].payload.event).toMatchObject({ status: "pending" })
  act(() => result.current.applyRunMessageEvent(toolEvent("tool-started", { tool_name: "calculator" }), "run-1"))
  expect(result.current.messages[0].payload.event).toMatchObject({ status: "running" })
  act(() => result.current.applyRunMessageEvent(toolEvent("tool-finished", { output: "3" }), "run-1"))
  expect(result.current.messages).toHaveLength(1)
  expect(result.current.messages[0].payload.event).toMatchObject({
    status: "completed", name: "calculator", args: { a: 1, b: 2 }, output: "3",
  })
})

it.each([
  ["tool-error", { message: "Command failed" }, "Command failed"],
  ["tool-finished", { output: { status: "error", content: "Permission denied" } }, undefined],
])("handles %s as a failed tool", (event, fields, error) => {
  const { result } = renderHook(() => useChatMessages())
  act(() => {
    result.current.applyRunMessageEvent(toolEvent("tool-started", { tool_name: "execute" }), "run-1")
    result.current.applyRunMessageEvent(toolEvent(event, fields), "run-1")
  })
  expect(result.current.messages).toHaveLength(1)
  expect(result.current.messages[0].payload.event).toMatchObject({ name: "execute", status: "error" })
  if (error) expect(result.current.messages[0].payload.event).toHaveProperty("error", error)
})

it("keeps reasoning separate from body text without duplicating the additional_kwargs copy", () => {
  const { result } = renderHook(() => useChatMessages())
  act(() => {
    result.current.applyRunMessageEvent(streamEvent("messages", { items: [{ stream_event: [
      { type: "message_delta", message_id: "assistant-1", reasoning_content_delta: "Let me ", additional_kwargs_reasoning_content: "Let me " },
      { type: "message_delta", message_id: "assistant-1", additional_kwargs_reasoning_content: "check.", content_delta: "The answer is 3." },
    ] }] }), "run-1")
    result.current.flushStream("thread-1")
  })
  expect(result.current.messages.map((message) => message.payload.event)).toMatchObject([
    { type: "reasoning", content: "Let me check." }, { content: "The answer is 3." },
  ])
})

it("clears buffered text and interaction routing before reusing a call id", () => {
  vi.useFakeTimers()
  const { result } = renderHook(() => useChatMessages())
  act(() => {
    result.current.applyRunMessageEvent(toolEvent("tool-started", { tool_name: "ask_user" }), "run-1")
    result.current.applyRunMessageEvent(streamEvent("messages", { items: [{ stream_event: [
      { type: "message_delta", message_id: "assistant-1", content_delta: "Previous thread" },
    ] }] }), "run-1")
    result.current.clearMessages()
    vi.advanceTimersByTime(1000)
  })
  expect(result.current.messages).toEqual([])
  act(() => result.current.applyRunMessageEvent(toolEvent("tool-started", { tool_name: "calculator" }), "run-1"))
  expect(result.current.messages).toHaveLength(1)
  expect(result.current.messages[0].payload.event).toMatchObject({ name: "calculator", status: "running" })
})
