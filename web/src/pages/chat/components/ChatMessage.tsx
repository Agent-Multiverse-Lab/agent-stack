import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Brain, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { ThreadMessageAttachmentResponse } from "@/types/attachment";
import type { ChatMessage as ChatMessageType } from "@/types/chat";
import { Attachment } from "@/pages/chat/components/Attachment";
import { ToolCall } from "@/pages/chat/components/ToolCall";
import { useTranslation } from "@/i18n";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;
const isAttachment = (
  value: unknown,
): value is ThreadMessageAttachmentResponse =>
  isRecord(value) && typeof value.file_id === "string";

function AgentTasks({ event }: { event: Record<string, unknown> }) {
  const { t } = useTranslation();
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
  return (
    <Collapsible defaultOpen className="group/task-list w-full max-w-2xl text-sm">
      <CollapsibleTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-auto px-1 py-1 text-xs text-muted-foreground"
          />
        }
      >
        <ChevronRight className="transition-transform group-data-open/task-list:rotate-90" />
        <span>
          {t(todos.length === 1 ? "{{tasks}} task" : "{{tasks}} tasks", {
            tasks: todos.length,
          })} {" · "}
          {t("{{completed}} completed", {
            completed: todos.filter((item) => item.status === "completed")
              .length,
          })}
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-1.5 grid gap-1">
        {todos.map((todo, index) => (
          <Collapsible
            key={`${todo.content}-${index}`}
            className="group/task"
          >
            <CollapsibleTrigger
              render={
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-auto w-full justify-start px-1 py-1 text-left text-xs"
                />
              }
            >
              <ChevronRight className="transition-transform group-data-open/task:rotate-90" />
              <span className="font-medium">
                {todo.status === "in_progress"
                  ? t("In progress")
                  : todo.status === "completed"
                    ? t("Completed")
                    : t("Pending")}
              </span>
              <span className="truncate text-muted-foreground">
                {todo.content}
              </span>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <pre className="ml-4 overflow-x-auto border-l border-border py-1 pl-3 text-[11.5px] text-muted-foreground">
                {JSON.stringify(todo, null, 2)}
              </pre>
            </CollapsibleContent>
          </Collapsible>
        ))}
      </CollapsibleContent>
    </Collapsible>
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
