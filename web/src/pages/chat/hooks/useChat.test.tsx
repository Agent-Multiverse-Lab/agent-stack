import { afterEach, expect, it, vi } from "vitest"
import { act, renderHook } from "@testing-library/react"

import { useChat } from "@/pages/chat/hooks/useChat"
import type { AgentRunStreamEvent } from "@/types/chat"

afterEach(() => vi.useRealTimers())

it("smooths a burst before flushing the complete text", () => {
  vi.useFakeTimers()
  const { result } = renderHook(() => useChat())
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
  expect((result.current.state.messages[0].payload.event as { content: string }).content).toBe("")

  act(() => vi.advanceTimersByTime(240))
  const partial = (result.current.state.messages[0].payload.event as { content: string }).content
  expect(partial.length).toBeGreaterThan(0)
  expect(partial.length).toBeLessThan(content.length)

  act(() => result.current.flushStream("thread-1"))
  expect((result.current.state.messages[0].payload.event as { content: string }).content).toBe(content)
})

it("merges streamed text and assigns distinct optimistic message ids", () => {
  const { result } = renderHook(() => useChat())
  const event: AgentRunStreamEvent = {
    id: "1",
    scope: "agent_run",
    type: "messages",
    run_id: "run-1",
    thread_id: "thread-1",
    created_at: new Date().toISOString(),
    items: [{
      stream_event: [
        { type: "message_delta", message_id: "assistant-1", content_delta: "Hello" },
        { type: "message_delta", message_id: "assistant-1", content_delta: " world" }
      ]
    }]
  }
  act(() => {
    result.current.applyRunMessageEvent(event, "run-1")
    result.current.flushStream("thread-1")
  })
  const assistant = result.current.state.messages[0]
  expect((assistant.payload.event as { content: string }).content).toBe("Hello world")

  let firstId = 0
  let secondId = 0
  act(() => {
    result.current.update({ draft: "First" })
    firstId = result.current.beginSubmission()!.optimisticMessageId
    result.current.update({ submitting: false, draft: "Second" })
    secondId = result.current.beginSubmission()!.optimisticMessageId
  })
  expect(firstId).toBe(-1)
  expect(secondId).toBe(-2)
})
