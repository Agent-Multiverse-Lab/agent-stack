import { beforeEach, expect, it, vi } from "vitest"

import { apiClient } from "@/api/client"
import { createAgentRun, resumeAgentRun } from "@/api/agent-run"
import type { AgentRunCreateRequest } from "@/api/agent-run"

vi.mock("@/api/client", () => ({ apiClient: { apiPost: vi.fn() } }))
vi.mock("@/i18n", () => ({ default: { t: (value: string) => value } }))

beforeEach(() => vi.clearAllMocks())

it("sends model and attachments in the chat request metadata with default enqueue policy", async () => {
  await createAgentRun("Analyze", "LeaderAgent", "thread-1", ["file-1"], "provider/model")
  expect(apiClient.apiPost).toHaveBeenCalledWith(
    "/api/agent/runs",
    {
      query: "Analyze",
      dispatch_policy: "enqueue",
      agent_id: "LeaderAgent",
      thread_id: "thread-1",
      request_metadata: {
        type: "chat",
        model: "provider/model",
        attachment_file_ids: ["file-1"],
      },
    },
    { requiresAuth: true },
  )

  await createAgentRun("Reject busy", "LeaderAgent", "thread-1", [], undefined, "reject")
  expect(apiClient.apiPost).toHaveBeenLastCalledWith(
    "/api/agent/runs",
    expect.objectContaining({ dispatch_policy: "reject" }),
    { requiresAuth: true },
  )

  await createAgentRun("Steer busy", "LeaderAgent", "thread-1", [], undefined, "steer")
  expect(apiClient.apiPost).toHaveBeenLastCalledWith(
    "/api/agent/runs",
    expect.objectContaining({ dispatch_policy: "steer" }),
    { requiresAuth: true },
  )
})

it("uses the shared request for the resume endpoint", async () => {
  const request: AgentRunCreateRequest = {
    agent_id: "LeaderAgent",
    thread_id: "thread-1",
    request_metadata: {
      type: "resume",
      request_id: "resume-request-1",
      resume: { answers: { database: "postgresql" } },
    },
  }
  await resumeAgentRun("parent-run", request)
  expect(apiClient.apiPost).toHaveBeenCalledWith(
    "/api/agent/runs/parent-run/resume", request, { requiresAuth: true },
  )
})
