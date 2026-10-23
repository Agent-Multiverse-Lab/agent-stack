import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"

import { listAgents, getAgentContext, updateAgent } from "@/api/agent"
import AgentPage from "@/pages/agent/AgentPage"
import { installBrowserStubs } from "@/test/browserStubs"
import type { Agent } from "@/types/agent"

vi.mock("@/api/agent", () => ({ listAgents: vi.fn(), getAgentContext: vi.fn(), updateAgent: vi.fn() }))

const agentList: Agent[] = [
  {
    id: "research-agent",
    name: "DB research",
    description: "Research description from the database",
    is_subagent: false,
    enabled: true,
  },
  {
    id: "LeaderAgent",
    name: "DB coordinator",
    description: "Coordinator description from the database",
    is_subagent: false,
    enabled: true,
  },
  {
    id: "offline-agent",
    name: "DB offline",
    description: "Disabled description from the database",
    is_subagent: false,
    enabled: false,
  },
  {
    id: "specialist-agent",
    name: "DB specialist",
    description: "Specialist description from the database",
    is_subagent: true,
    enabled: true,
  },
]

beforeEach(() => {
  installBrowserStubs()
  vi.mocked(listAgents).mockResolvedValue(agentList)
  vi.mocked(getAgentContext).mockResolvedValue({
    model: "provider/model", system_prompt: "Persisted system prompt", summary_threshold: 64,
    summary_keep_messages: 8, summary_tool_result_token_limit: 250, summary_prompt: "Summarize findings",
    tools: ["search"], mcps: ["documents"], skill_root: "/skills",
  })
})

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
  vi.unstubAllGlobals()
})

it("shows database names and descriptions with the leader before separate agent and subagent groups", async () => {
  render(<AgentPage />)

  const leader = await screen.findByRole("article", { name: "DB coordinator" })
  expect(within(leader).getByText("Coordinator description from the database")).toBeTruthy()
  expect(screen.getAllByRole("region")).toEqual([
    screen.getByRole("region", { name: "Main agent" }),
    screen.getByRole("region", { name: /^Agents/ }),
    screen.getByRole("region", { name: /^Sub agents/ }),
  ])

  const main = within(screen.getByRole("region", { name: "Main agent" }))
  expect(main.getAllByRole("article")).toEqual([leader])

  const agents = within(screen.getByRole("region", { name: /^Agents/ }))
  expect(agents.getAllByRole("article").map((article) => article.getAttribute("aria-label")))
    .toEqual(["DB research", "DB offline"])
  expect(agents.getByText("Research description from the database")).toBeTruthy()
  expect(agents.queryByRole("article", { name: "DB specialist" })).toBeNull()
  expect(within(agents.getByRole("article", { name: "DB offline" })).getByText("Disabled")).toBeTruthy()
  expect(within(agents.getByRole("article", { name: "DB research" })).queryByText("Disabled")).toBeNull()

  const subagents = within(screen.getByRole("region", { name: /^Sub agents/ }))
  expect(subagents.getAllByRole("article")).toEqual([
    subagents.getByRole("article", { name: "DB specialist" }),
  ])
  expect(subagents.getByText("Specialist description from the database")).toBeTruthy()
})

it("shows a failed request and retries to load the agents", async () => {
  vi.mocked(listAgents)
    .mockRejectedValueOnce(new Error("Agent service unavailable"))
    .mockResolvedValueOnce(agentList)
  render(<AgentPage />)

  const alert = await screen.findByRole("alert")
  expect(within(alert).getByText("Agent service unavailable")).toBeTruthy()
  fireEvent.click(within(alert).getByRole("button", { name: "Retry" }))

  expect(await screen.findByRole("article", { name: "DB coordinator" })).toBeTruthy()
  await waitFor(() => expect(listAgents).toHaveBeenCalledTimes(2))
  expect(screen.queryByRole("alert")).toBeNull()
})

it("shows the empty state without agent cards or group headings", async () => {
  vi.mocked(listAgents).mockResolvedValue([])
  render(<AgentPage />)

  expect(await screen.findByText("No agents yet")).toBeTruthy()
  expect(screen.queryByRole("article")).toBeNull()
  expect(screen.queryByRole("region")).toBeNull()
})

it("shows a subagent-only list without inventing a leader or ordinary agents", async () => {
  vi.mocked(listAgents).mockResolvedValue(agentList.filter((agent) => agent.is_subagent))
  render(<AgentPage />)

  expect(await screen.findByRole("article", { name: "DB specialist" })).toBeTruthy()
  expect(screen.getAllByRole("region")).toEqual([
    screen.getByRole("region", { name: /^Sub agents/ }),
  ])
  expect(screen.queryByText("No agents yet")).toBeNull()
  expect(screen.queryByRole("region", { name: "Main agent" })).toBeNull()
})

it("shows an empty subagent group when only a main agent exists", async () => {
  vi.mocked(listAgents).mockResolvedValue(
    agentList.filter((agent) => agent.id === "LeaderAgent")
  )
  render(<AgentPage />)

  expect(await screen.findByRole("article", { name: "DB coordinator" })).toBeTruthy()
  expect(within(screen.getByRole("region", { name: /^Sub agents/ })).getByText("No subagents yet"))
    .toBeTruthy()
  expect(screen.queryByRole("region", { name: /^Agents/ })).toBeNull()
})

it("opens the main agent details, closes with Escape, and opens a different agent", async () => {
  render(<AgentPage />)

  fireEvent.click(await screen.findByRole("button", { name: "View DB coordinator details" }))
  const mainDialog = await screen.findByRole("dialog", { name: "DB coordinator" })
  const mainDetails = within(mainDialog)
  expect(mainDetails.getByRole("heading", { name: "DB coordinator" })).toBeTruthy()
  expect((mainDetails.getByRole("textbox", { name: "Agent name" }) as HTMLInputElement).value)
    .toBe("DB coordinator")
  expect((mainDetails.getByRole("textbox", { name: "Description" }) as HTMLTextAreaElement).value)
    .toBe("Coordinator description from the database")
  expect(mainDetails.getByText("Agent ID")).toBeTruthy()
  expect(mainDetails.getByText("LeaderAgent")).toBeTruthy()
  expect(mainDetails.getByText("Agent type")).toBeTruthy()
  expect(mainDetails.getByText("Main agent")).toBeTruthy()
  expect(mainDetails.getByRole("switch", { name: "Enable agent" }).getAttribute("aria-checked"))
    .toBe("true")
  const prompt = await mainDetails.findByRole("textbox", { name: "System prompt" }) as HTMLTextAreaElement
  expect(prompt.value).toBe("Persisted system prompt")
  expect(prompt.readOnly).toBe(true)
  expect(mainDetails.getByText("64 K tokens")).toBeTruthy()
  expect(mainDetails.getByText("documents")).toBeTruthy()
  expect(getAgentContext).toHaveBeenCalledWith("LeaderAgent", expect.any(AbortSignal))

  fireEvent.keyDown(mainDialog, { key: "Escape", code: "Escape" })
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())

  fireEvent.click(screen.getByRole("button", { name: "View DB research details" }))
  const researchDialog = await screen.findByRole("dialog", { name: "DB research" })
  const researchDetails = within(researchDialog)
  expect((researchDetails.getByRole("textbox", { name: "Description" }) as HTMLTextAreaElement).value)
    .toBe("Research description from the database")
  expect(researchDetails.getByText("research-agent")).toBeTruthy()
  expect(researchDetails.getByText("Agent")).toBeTruthy()
  expect(researchDetails.queryByText("Coordinator description from the database")).toBeNull()

  fireEvent.click(researchDetails.getByRole("button", { name: "Close" }))
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
})

it("allows inspecting disabled agents and separately opens subagent details", async () => {
  render(<AgentPage />)

  const disabledTrigger = await screen.findByRole("button", { name: "View DB offline details" })
  expect(disabledTrigger.hasAttribute("disabled")).toBe(false)
  fireEvent.click(disabledTrigger)
  const disabledDialog = await screen.findByRole("dialog", { name: "DB offline" })
  const disabledDetails = within(disabledDialog)
  expect((disabledDetails.getByRole("textbox", { name: "Description" }) as HTMLTextAreaElement).value)
    .toBe("Disabled description from the database")
  expect(disabledDetails.getByText("offline-agent")).toBeTruthy()
  expect(disabledDetails.getByText("Agent")).toBeTruthy()
  expect(disabledDetails.getByRole("switch", { name: "Enable agent" }).getAttribute("aria-checked"))
    .toBe("false")

  fireEvent.click(disabledDetails.getByRole("button", { name: "Close" }))
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())

  fireEvent.click(screen.getByRole("button", { name: "View DB specialist details" }))
  const subagentDialog = await screen.findByRole("dialog", { name: "DB specialist" })
  const subagentDetails = within(subagentDialog)
  expect((subagentDetails.getByRole("textbox", { name: "Description" }) as HTMLTextAreaElement).value)
    .toBe("Specialist description from the database")
  expect(subagentDetails.getByText("specialist-agent")).toBeTruthy()
  expect(subagentDetails.getByText("Sub agent")).toBeTruthy()
  expect(subagentDetails.getByRole("switch", { name: "Enable agent" }).getAttribute("aria-checked"))
    .toBe("true")
  expect(subagentDetails.queryByText("offline-agent")).toBeNull()

  fireEvent.click(subagentDetails.getByRole("button", { name: "Close" }))
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
})

it("saves edited fields, prevents closing while saving, and reopens the updated main agent", async () => {
  const updated: Agent = {
    ...agentList[1]!,
    name: "Saved coordinator",
    description: "Updated description from the database",
    enabled: false,
  }
  let resolveUpdate!: (agent: Agent) => void
  vi.mocked(updateAgent).mockReturnValue(new Promise((resolve) => { resolveUpdate = resolve }))
  render(<AgentPage />)

  fireEvent.click(await screen.findByRole("button", { name: "View DB coordinator details" }))
  const dialog = await screen.findByRole("dialog", { name: "DB coordinator" })
  const details = within(dialog)
  fireEvent.change(details.getByRole("textbox", { name: "Agent name" }), {
    target: { value: "  Saved coordinator  " },
  })
  fireEvent.change(details.getByRole("textbox", { name: "Description" }), {
    target: { value: updated.description },
  })
  fireEvent.click(details.getByRole("switch", { name: "Enable agent" }))
  fireEvent.click(details.getByRole("button", { name: "Save changes" }))

  await waitFor(() => expect(updateAgent).toHaveBeenCalledWith("LeaderAgent", {
    name: "Saved coordinator",
    description: updated.description,
    enabled: false,
  }))
  expect(details.getByRole("button", { name: /Saving/ }).hasAttribute("disabled")).toBe(true)
  expect(details.getByRole("button", { name: "Cancel" }).hasAttribute("disabled")).toBe(true)
  fireEvent.keyDown(dialog, { key: "Escape", code: "Escape" })
  expect(screen.getByRole("dialog", { name: "DB coordinator" })).toBeTruthy()
  expect(updateAgent).toHaveBeenCalledTimes(1)

  await act(async () => resolveUpdate(updated))
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  const main = within(screen.getByRole("region", { name: "Main agent" }))
  const updatedCard = main.getByRole("article", { name: "Saved coordinator" })
  expect(within(updatedCard).getByText(updated.description)).toBeTruthy()
  expect(within(updatedCard).getByText("Disabled")).toBeTruthy()
  expect(screen.queryByRole("article", { name: "DB coordinator" })).toBeNull()

  fireEvent.click(screen.getByRole("button", { name: "View Saved coordinator details" }))
  const savedDetails = within(await screen.findByRole("dialog", { name: "Saved coordinator" }))
  expect((savedDetails.getByRole("textbox", { name: "Agent name" }) as HTMLInputElement).value)
    .toBe(updated.name)
  expect((savedDetails.getByRole("textbox", { name: "Description" }) as HTMLTextAreaElement).value)
    .toBe(updated.description)
  expect(savedDetails.getByRole("switch", { name: "Enable agent" }).getAttribute("aria-checked"))
    .toBe("false")
})

it.each(["Cancel", "Close", "Escape"])("discards the unsaved draft when closing with %s", async (closeAction) => {
  render(<AgentPage />)

  fireEvent.click(await screen.findByRole("button", { name: "View DB research details" }))
  const dialog = await screen.findByRole("dialog", { name: "DB research" })
  const details = within(dialog)
  fireEvent.change(details.getByRole("textbox", { name: "Agent name" }), {
    target: { value: "Unsaved name" },
  })
  fireEvent.change(details.getByRole("textbox", { name: "Description" }), {
    target: { value: "Unsaved description" },
  })
  fireEvent.click(details.getByRole("switch", { name: "Enable agent" }))
  if (closeAction === "Escape") {
    fireEvent.keyDown(dialog, { key: "Escape", code: "Escape" })
  } else {
    fireEvent.click(details.getByRole("button", { name: closeAction }))
  }
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  expect(updateAgent).not.toHaveBeenCalled()
  expect(screen.getByRole("article", { name: "DB research" })).toBeTruthy()

  fireEvent.click(screen.getByRole("button", { name: "View DB research details" }))
  const reopened = within(await screen.findByRole("dialog", { name: "DB research" }))
  expect((reopened.getByRole("textbox", { name: "Agent name" }) as HTMLInputElement).value)
    .toBe("DB research")
  expect((reopened.getByRole("textbox", { name: "Description" }) as HTMLTextAreaElement).value)
    .toBe("Research description from the database")
  expect(reopened.getByRole("switch", { name: "Enable agent" }).getAttribute("aria-checked"))
    .toBe("true")
})

it("keeps the draft after a failed save and retries it successfully", async () => {
  const updated: Agent = {
    ...agentList[3]!,
    name: "Updated specialist",
    description: "A draft worth keeping",
  }
  vi.mocked(updateAgent)
    .mockRejectedValueOnce(new Error("Agent update unavailable"))
    .mockResolvedValueOnce(updated)
  render(<AgentPage />)

  fireEvent.click(await screen.findByRole("button", { name: "View DB specialist details" }))
  const details = within(await screen.findByRole("dialog", { name: "DB specialist" }))
  fireEvent.change(details.getByRole("textbox", { name: "Agent name" }), {
    target: { value: updated.name },
  })
  fireEvent.change(details.getByRole("textbox", { name: "Description" }), {
    target: { value: updated.description },
  })
  fireEvent.click(details.getByRole("button", { name: "Save changes" }))

  expect(await details.findByRole("alert")).toBeTruthy()
  expect(details.getByText("Agent update unavailable")).toBeTruthy()
  expect((details.getByRole("textbox", { name: "Agent name" }) as HTMLInputElement).value)
    .toBe(updated.name)
  expect((details.getByRole("textbox", { name: "Description" }) as HTMLTextAreaElement).value)
    .toBe(updated.description)
  fireEvent.click(details.getByRole("button", { name: "Save changes" }))

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  expect(updateAgent).toHaveBeenCalledTimes(2)
  expect(updateAgent).toHaveBeenLastCalledWith("specialist-agent", {
    name: updated.name,
    description: updated.description,
    enabled: true,
  })
  expect(within(screen.getByRole("region", { name: /^Sub agents/ }))
    .getByRole("article", { name: updated.name })).toBeTruthy()
})

it("rejects a whitespace-only name and lets a disabled agent be enabled and saved", async () => {
  const updated: Agent = { ...agentList[2]!, enabled: true }
  vi.mocked(updateAgent).mockResolvedValue(updated)
  render(<AgentPage />)

  fireEvent.click(await screen.findByRole("button", { name: "View DB offline details" }))
  const details = within(await screen.findByRole("dialog", { name: "DB offline" }))
  const nameInput = details.getByRole("textbox", { name: "Agent name" })
  fireEvent.change(nameInput, { target: { value: "   " } })
  const save = details.getByRole("button", { name: "Save changes" })
  expect(save.hasAttribute("disabled")).toBe(true)
  fireEvent.click(save)
  expect(updateAgent).not.toHaveBeenCalled()

  fireEvent.change(nameInput, { target: { value: "DB offline" } })
  fireEvent.click(details.getByRole("switch", { name: "Enable agent" }))
  expect(details.getByRole("switch", { name: "Enable agent" }).getAttribute("aria-checked"))
    .toBe("true")
  fireEvent.click(details.getByRole("button", { name: "Save changes" }))

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  expect(updateAgent).toHaveBeenCalledWith("offline-agent", {
    name: "DB offline",
    description: "Disabled description from the database",
    enabled: true,
  })
  expect(within(screen.getByRole("article", { name: "DB offline" })).queryByText("Disabled"))
    .toBeNull()
})

it("renders the top header with the Agent title and refresh action", async () => {
  render(<AgentPage />)
  await screen.findByRole("article", { name: "DB coordinator" })
  expect(screen.getByRole("heading", { name: "Agent", level: 1 })).toBeTruthy()
  expect(screen.getByRole("main", { name: "Agent" })).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: "Refresh agents" }))
  await waitFor(() => expect(listAgents).toHaveBeenCalledTimes(2))
  expect(await screen.findByRole("heading", { name: "Main agent" })).toBeTruthy()
})
