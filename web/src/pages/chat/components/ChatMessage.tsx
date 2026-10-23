import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Brain, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { ThreadMessageAttachmentResponse } from "@/api/attachment";
import type { ChatMessage as ChatMessageType } from "@/pages/chat/types";
import { Attachment } from "@/pages/chat/components/Attachment";
import {
  TaskCheckIcon,
  TaskChevron,
  TaskSpinnerRing,
  TaskStatusBadge,
  ToolCall,
} from "@/pages/chat/components/ToolCall";
import { useTranslation } from "@/i18n";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;
const isAttachment = (
  value: unknown,
): value is ThreadMessageAttachmentResponse =>
  isRecord(value) && typeof value.file_id === "string";

function AgentTasks({ event }: { event: Record<string, unknown> }) {
  const { t } = useTranslation();
  const [manualOpen, setManualOpen] = useState<Record<string, boolean>>({});
  const state = isRecord(event.agent_state) ? event.agent_state : {};
  const todos = Array.isArray(state.agent_todo)
    ? state.agent_todo.filter(
        (item): item is { content: string; status: string } =>
          isRecord(item) &&
          typeof item.content === "string" &&
          ["pending", "in_progress", "completed"].includes(String(item.status)),
      )
    : [];
  if (!todos.length) return null;

  const completedCount = todos.filter(
    (item) => item.status === "completed",
  ).length;
  const allCompleted = completedCount === todos.length;

  return (
    <div
      data-task-group-status={allCompleted ? "completed" : "running"}
      className="flex w-full max-w-2xl min-w-0 flex-col gap-0 self-start overflow-hidden rounded-[14px] border border-border bg-card text-card-foreground shadow-sm"
    >
      <div className="flex h-9 items-center justify-between border-b border-border bg-muted/30 px-3 text-xs">
        <span className="font-medium text-foreground">
          {t(todos.length === 1 ? "{{tasks}} task" : "{{tasks}} tasks", {
            tasks: todos.length,
          })}
        </span>
        <span className="tabular-nums text-muted-foreground">
          {t("{{completed}} completed", {
            completed: completedCount,
          })}
        </span>
      </div>

      {todos.map((todo, i) => {
        const rowKey = `${todo.content}-${i}`;
        const open = manualOpen[rowKey] ?? false;
        const statusLabel =
          todo.status === "in_progress"
            ? t("In progress")
            : todo.status === "completed"
              ? t("Completed")
              : t("Pending");

        return (
          <div
            key={rowKey}
            className="self-stretch overflow-hidden border-b border-border transition-colors duration-300 last:border-0 hover:bg-accent/50"
            style={{
              animation: `task-fade-up 450ms cubic-bezier(0.23,1,0.32,1) ${i * 80}ms both`,
            }}
          >
            <Button
              type="button"
              variant="ghost"
              aria-expanded={open}
              onClick={() =>
                setManualOpen((current) => ({ ...current, [rowKey]: !open }))
              }
              className="flex h-11 w-full items-center justify-start gap-2.5 rounded-none px-2.5 py-0 text-left font-normal hover:bg-transparent"
            >
              <span
                className="flex size-6 shrink-0 items-center justify-center"
                data-task-status={todo.status}
                aria-hidden="true"
              >
                {todo.status === "completed" ? (
                  <TaskStatusBadge tone="green">{TaskCheckIcon}</TaskStatusBadge>
                ) : (
                  <TaskSpinnerRing active={todo.status === "in_progress"}>
                    {i + 1}
                  </TaskSpinnerRing>
                )}
              </span>
              <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-foreground">
                {todo.content}
              </span>
              {todo.status === "completed" ? (
                <span className="inline-flex h-5.5 items-center rounded-full border border-success-border bg-success-muted px-2 text-[11.5px] font-medium text-success">
                  {statusLabel}
                </span>
              ) : (
                <span className="text-[12px] text-muted-foreground tabular-nums">
                  {statusLabel}
                </span>
              )}
              <TaskChevron open={open} />
            </Button>

            <div
              className="grid transition-[grid-template-rows,opacity] duration-300 motion-reduce:transition-none"
              style={{
                gridTemplateRows: open ? "1fr" : "0fr",
                opacity: open ? 1 : 0,
                transitionTimingFunction: "cubic-bezier(0.23, 1, 0.32, 1)",
              }}
            >
              <div className="overflow-hidden">
                {open && (
                  <div className="mb-2.5 grid grid-cols-[24px_minmax(0,1fr)] gap-2.5 px-2.5 pt-0.5">
                    <span aria-hidden="true" className="mx-auto h-full w-px bg-border" />
                    <div
                      className="flex flex-col gap-1.5"
                      style={{
                        animation:
                          "task-fade-up 300ms cubic-bezier(0.23,1,0.32,1) 120ms both",
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[12px] text-muted-foreground">
                          {t("Status")}
                        </span>
                        <span className="font-mono text-[11.5px] text-muted-foreground tabular-nums">
                          {todo.status}
                        </span>
                      </div>
                      <pre className="m-0 overflow-x-auto rounded-md border border-border bg-muted/50 px-2.5 py-1.5 font-mono text-[11.5px] leading-5 text-muted-foreground">
                        {JSON.stringify(todo, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ChatMessage({ message }: { message: ChatMessageType }) {
  const event = isRecord(message.payload.event) ? message.payload.event : {};
  const content = typeof event.content === "string" ? event.content : "";
  const attachments = Array.isArray(event.attachments)
    ? event.attachments.filter(isAttachment)
    : [];
  if (message.type === "human")
    return (
      <article className="flex justify-end">
        <div className="my-[0.8rem] max-w-[95%] rounded-lg bg-message px-4 py-2 text-sm leading-6 tracking-[0.25px] text-foreground">
          {content && (
            <p className="m-0 whitespace-pre-wrap leading-6">{content}</p>
          )}
          {attachments.length > 0 && (
            <ul
              className={`m-0 flex list-none flex-wrap gap-2 p-0 ${content ? "mt-3" : ""}`}
            >
              {attachments.map((item) => (
                <Attachment key={item.file_id} attachment={item} />
              ))}
            </ul>
          )}
        </div>
      </article>
    );
  if (message.payload.type === "tool") {
    if (event.type === "tool_call") return <ToolCall event={event} />;
    if (event.type === "reasoning") return <Reasoning content={content} />;
    return <AgentTasks event={event} />;
  }
  return (
    <article className="min-w-0 max-w-full text-sm leading-6 tracking-[0.25px] text-foreground">
      {content && (
        <div className="chat-markdown max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      )}
      {attachments.length > 0 && (
        <ul className="mt-3 flex list-none flex-wrap gap-2 p-0">
          {attachments.map((item) => (
            <Attachment key={item.file_id} attachment={item} />
          ))}
        </ul>
      )}
    </article>
  );
}

function Reasoning({ content }: { content: string }) {
  const { t } = useTranslation();
  if (!content) return null;
  const preview = content.trim().split(/\r?\n/).at(-1) ?? "";
  return (
    <Collapsible className="group/reasoning w-full max-w-2xl min-w-0 text-sm">
      <CollapsibleTrigger aria-label={`${t("Reasoning")} ${preview}`} render={
        <Button type="button" variant="ghost" size="sm"
          className="h-auto max-w-full justify-start px-1 py-1 text-xs text-muted-foreground" />
      }>
        <ChevronRight className="shrink-0 transition-transform group-data-open/reasoning:rotate-90" />
        <Brain className="shrink-0" />
        <span className="shrink-0">{t("Reasoning")}</span>
        <span className="truncate">{preview}</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-1.5 ml-3 max-h-72 overflow-auto whitespace-pre-wrap break-words border-l border-border py-1 pl-3 text-xs leading-5 text-muted-foreground">
        {content}
      </CollapsibleContent>
    </Collapsible>
  );
}
