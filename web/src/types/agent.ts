export type Agent = {
  id: string
  name: string
  description: string
  is_subagent: boolean
  enabled: boolean
}

export type AgentSummary = Pick<Agent, "id" | "name" | "description">
