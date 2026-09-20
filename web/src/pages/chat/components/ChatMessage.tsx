import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { ThreadMessageAttachmentResponse } from "@/types/attachment";
import type { ChatMessage as ChatMessageType } from "@/types/chat";
import { Attachment } from "@/pages/chat/components/Attachment";
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
        <div className="max-w-[min(82%,42rem)] rounded-[1.15rem] bg-muted px-4 py-2.5 text-foreground">
          {content && (
            <p className="m-0 whitespace-pre-wrap leading-7">{content}</p>
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
  if (message.payload.type === "tool") return <AgentTasks event={event} />;
  return (
    <article className="min-w-0 max-w-full leading-7 text-foreground">
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
