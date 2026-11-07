import type { AgentContentBlock, ChatRenderItem } from "@/pages/chat/types"
import { Thinking } from "@/pages/chat/components/Thinking"
import { ArtifactList } from "@/pages/chat/components/ArtifactCard"
import { ToolCall } from "@/pages/chat/components/ToolCall"
import { AgentMarkdownSection } from "./AgentMarkdownSection"
import { AgentReasoningSection } from "./AgentReasoningSection"
import { AgentTasksSection } from "./AgentTasksSection"

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
  const hasAnswer = Boolean(item.answerBlock)
  const isProcessActive = item.active && !hasAnswer

  const label = item.waiting
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

  const showProcess = item.processBlocks.length > 0 || isProcessActive || item.waiting

  return (
    <section className="grid min-w-0 gap-4" data-run-id={item.runId}>
      {showProcess && (
        <Thinking
          label={label}
          active={isProcessActive}
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
