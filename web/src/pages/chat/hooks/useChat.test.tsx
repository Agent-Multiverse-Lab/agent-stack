import { expect, it } from "vitest"
import { act, renderHook } from "@testing-library/react"

import { useChat } from "@/pages/chat/hooks/useChat"
import type { AgentRunStreamEvent } from "@/types/chat"

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
  act(() => result.current.applyRunMessageEvent(event, "run-1"))
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
