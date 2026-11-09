import type { AgentContentBlock, ChatRenderItem } from "@/pages/chat/types"
import { Thinking } from "@/pages/chat/components/Thinking"
import { ArtifactList } from "@/pages/chat/components/ArtifactCard"
import { ToolCall } from "@/pages/chat/components/ToolCall"
import { AgentMarkdownSection } from "./AgentMarkdownSection"
import { AgentReasoningSection } from "./AgentReasoningSection"
import { AgentTasksSection } from "./AgentTasksSection"
import { toolLabels } from "@/pages/chat/tool-labels"
import { useTranslation } from "@/i18n"

type AgentRunItem = Extract<ChatRenderItem, { kind: "agent_run" }>

interface AgentRunSectionProps {
  item: AgentRunItem
}

export function AgentBlockSwitch({ block }: { block: AgentContentBlock }) {
  switch (block.kind) {
    case "tool_call":
      return <ToolCall block={block} />
    case "reasoning":
      return <AgentReasoningSection content={block.content} />
    case "agent_tasks":
      return <AgentTasksSection todos={block.todos} />
    case "markdown":
      return (
        <AgentMarkdownSection
          content={block.content}
          attachments={block.attachments}
          className="text-sm leading-6 text-foreground"
        />
      )
  }
}

export function AgentRunSection({ item }: AgentRunSectionProps) {
  const { t } = useTranslation()
  const hasAnswer = Boolean(item.answerBlock)
  const isProcessActive = item.active && !hasAnswer
  const toolBlocks = item.processBlocks.filter(
    (block): block is Extract<AgentContentBlock, { kind: "tool_call" }> =>
      block.kind === "tool_call",
  )
  const hasReasoning = item.processBlocks.some((block) => block.kind === "reasoning")
  const toolNames = [
    ...new Set(
      toolBlocks.map((block) => t(toolLabels.get(block.name) ?? block.name)),
    ),
  ]
  const visibleToolNames = toolNames.slice(0, 3)
  const toolMeta =
    toolBlocks.length > 1 && visibleToolNames.length > 0
      ? `${visibleToolNames.join(" · ")}${toolNames.length > visibleToolNames.length ? ` +${toolNames.length - visibleToolNames.length}` : ""}`
      : undefined
  const runningCount = toolBlocks.filter(
    (block) => block.status === "pending" || block.status === "running",
  ).length
  const errorCount = toolBlocks.filter((block) => block.status === "error").length
  const toolStatus = [
    errorCount > 0 ? t("{{count}} failed", { count: errorCount }) : "",
    runningCount > 0 ? t("{{count}} in progress", { count: runningCount }) : "",
  ]
    .filter(Boolean)
    .join(" · ") || undefined

  const lifecycleLabel = item.waiting
    ? "Waiting for your response"
    : item.status === "failed"
      ? "Execution failed"
      : item.status === "cancelled"
        ? "Cancelled"
        : item.status === "interrupted"
          ? "Interrupted"
          : isProcessActive
            ? item.processBlocks.length
              ? "Working"
              : "Thinking"
            : "Execution process"
  const label =
    toolBlocks.length === 0
      ? lifecycleLabel
      : hasReasoning
        ? t("Reasoning and tool calls · {{count}} tools", {
            count: toolBlocks.length,
          })
        : toolBlocks.length === 1
          ? t("Calling: {{tool}}", { tool: toolNames[0] })
          : t("Called {{count}} tools", { count: toolBlocks.length })

  const showProcess = item.processBlocks.length > 0 || isProcessActive || item.waiting

  return (
    <section className="grid min-w-0 gap-4" data-run-id={item.runId}>
      {showProcess && (
        <Thinking
          label={label}
          meta={toolMeta}
          status={toolStatus}
          active={isProcessActive}
          autoExpand={item.active}
        >
          {item.processBlocks.length > 0 ? (
            <div className="flex min-w-0 flex-col gap-2">
              {item.processBlocks.map((block) => (
                <AgentBlockSwitch
                  key={`${block.kind}:${block.kind === "tool_call" ? block.toolCallId : block.messageId}`}
                  block={block}
                />
              ))}
            </div>
          ) : undefined}
        </Thinking>
      )}

      {item.answerBlock && (
        <AgentMarkdownSection
          content={item.answerBlock.content}
          attachments={item.answerBlock.attachments}
        />
      )}

      {item.artifacts.length > 0 && (
        <ArtifactList artifacts={item.artifacts} threadId={item.threadId} />
      )}
    </section>
  )
}
