export interface AgentContext {
  system_prompt: string
  model: string
  summary_threshold: number
  summary_keep_messages: number
  summary_prompt: string
  summary_tool_result_token_limit: number
  tools: unknown[]
  mcps: string[]
  skill_root: string | null
}

export interface Agent {
  id: string
  name: string
  description: string
  is_subagent: boolean
  enabled: boolean
  context?: AgentContext | null
}
