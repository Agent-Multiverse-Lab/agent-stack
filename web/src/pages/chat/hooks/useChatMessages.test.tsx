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
