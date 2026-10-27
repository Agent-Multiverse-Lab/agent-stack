import { describe, expect, it } from "vitest"

import {
  artifactStatus,
  buildArtifactItems,
  extractArtifactsFromMessages,
  normalizeArtifacts,
  parseArtifactArguments,
} from "@/pages/chat/artifacts"
import type { ChatMessage } from "@/pages/chat/types"

const toolMessage = (event: Record<string, unknown>): ChatMessage => ({
  type: "ai",
  payload: { type: "tool", event: { type: "tool_call", ...event } },
})

describe("artifact helpers", () => {
  it("normalizes paths and parses streamed arguments", () => {
    expect(normalizeArtifacts(["/workspace/outputs/a.md", "", " /workspace/outputs/a.md ", "/x"])).toEqual([
      "/workspace/outputs/a.md",
      "/x",
    ])
    expect(parseArtifactArguments('{"filepaths":["/workspace/outputs/a.md"]}')).toEqual([
      "/workspace/outputs/a.md",
    ])
    expect(parseArtifactArguments("not-json")).toEqual([])
  })

  it("maps tool status to artifact status", () => {
    expect(artifactStatus("running")).toBe("generating")
    expect(artifactStatus("completed")).toBe("generated")
    expect(artifactStatus("error")).toBe("failed")
    expect(artifactStatus("cancelled")).toBe("failed")
  })

  it("extracts present_artifacts calls and keeps the latest status", () => {
    const messages = [
      toolMessage({
        name: "present_artifacts",
        args: { filepaths: ["/workspace/outputs/a.md"] },
        status: "running",
        thread_id: "thread-1",
      }),
      toolMessage({
        name: "present_artifacts",
        args: '{"filepaths":["/workspace/outputs/a.md","/workspace/outputs/b.png"]}',
        status: "completed",
        thread_id: "thread-1",
      }),
      toolMessage({
        name: "other_tool",
        args: { filepaths: ["/workspace/outputs/ignored.md"] },
        status: "completed",
      }),
    ]
    expect(extractArtifactsFromMessages(messages, "thread-1")).toEqual([
      { path: "/workspace/outputs/a.md", name: "a.md", status: "generated" },
      { path: "/workspace/outputs/b.png", name: "b.png", status: "generated" },
    ])
    expect(buildArtifactItems([
      { path: "/workspace/a", name: "a", status: "generated" },
      { path: "/workspace/b", name: "b", status: "generated" },
    ]).map((item) => item.path)).toEqual(["/workspace/b", "/workspace/a"])
  })
})
