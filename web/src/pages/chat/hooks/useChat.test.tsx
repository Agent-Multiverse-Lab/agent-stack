import { afterEach, expect, it } from "vitest"
import { act, cleanup, renderHook } from "@testing-library/react"

import { useChat } from "@/pages/chat/hooks/useChat"
import type { AgentRunStreamEvent, ThreadDetailResponse } from "@/types/chat"

afterEach(cleanup)

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

it("restores submitted input while removing only its optimistic message", () => {
  const { result } = renderHook(() => useChat())
  const attachment = {
    file_id: "file-1", file_name: "notes.txt", content_type: "text/plain", file_size: 12,
    bucket_name: "attachments", object_name: "notes.txt", access_url: "/files/file-1",
  }
  act(() => {
    result.current.update({ draft: "  Hello  " })
    result.current.appendUploadedAttachments([attachment])
    const submission = result.current.beginSubmission()!
    expect(submission.query).toBe("Hello")
    expect(result.current.getState()).toMatchObject({ draft: "", attachments: [], submitting: true })
    result.current.applyRunMessageEvent({
      id: "1", scope: "agent_run", type: "messages", run_id: "run-1", thread_id: "thread-1", created_at: null,
      items: [{ stream_event: [{ type: "message_delta", message_id: "assistant-1", content_delta: "Reply" }] }],
    }, "run-1")
    result.current.flushStream("thread-1")
    result.current.rollbackSubmission(submission)
    expect(result.current.getState().messages).toHaveLength(1)
  })
  expect(result.current.state.draft).toBe("  Hello  ")
  expect(result.current.state.attachments).toEqual([attachment])
  expect(result.current.state.messages[0].payload.event).toMatchObject({ content: "Reply" })
})

it("combines the latest input and message state through a retained getter", () => {
  const { result } = renderHook(() => useChat())
  const getState = result.current.getState
  act(() => {
    result.current.update({ draft: "Question" })
    result.current.beginSubmission()
    expect(getState().messages).toHaveLength(1)
    expect(getState().draft).toBe("")
  })
  act(() => {
    result.current.applyThreadDetail({
      thread: { thread_id: "thread-1", title: "Conversation" },
      messages: [{ message_id: 1, role: "user", content: "Question" }],
    } as ThreadDetailResponse)
    result.current.update({ draft: "Next" })
    expect(getState()).toMatchObject({
      thread: { thread_id: "thread-1" }, draft: "Next",
      messages: [{ payload: { event: { message_id: 1 } } }],
    })
    result.current.clearMessages()
    expect(getState().messages).toEqual([])
    expect(getState().draft).toBe("Next")
    result.current.resetThread()
    expect(getState()).toMatchObject({ thread: null, messages: [], draft: "", attachments: [] })
  })
})
