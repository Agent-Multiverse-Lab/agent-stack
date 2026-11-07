import { BookOpen, Bot, FileText, Folder, Plug, WandSparkles } from "lucide-react"
import type { ThreadMessageAttachmentResponse } from "@/api/attachment"
import {
  getMentionDisplayLabel,
  parseMentionText,
  type MentionType,
} from "@/pages/chat/mentions"
import { Attachment } from "@/pages/chat/components/Attachment"

function MentionTokenIcon({
  type,
  value,
}: {
  type: MentionType
  value: string
}) {
  if (type === "file") {
    return value.endsWith("/") ? (
      <Folder className="size-3.5 shrink-0" />
    ) : (
      <FileText className="size-3.5 shrink-0" />
    )
  }
  if (type === "knowledge") return <BookOpen className="size-3.5 shrink-0" />
  if (type === "agent") return <Bot className="size-3.5 shrink-0" />
  if (type === "skill") return <WandSparkles className="size-3.5 shrink-0" />
  return <Plug className="size-3.5 shrink-0" />
}

interface HumanMessageSectionProps {
  content: string
  attachments: ThreadMessageAttachmentResponse[]
}

export function HumanMessageSection({
  content,
  attachments,
}: HumanMessageSectionProps) {
  const segments = parseMentionText(content)

  return (
    <article className="flex justify-end">
      <div className="my-[0.8rem] max-w-[95%] rounded-lg bg-message px-4 py-2 text-sm leading-6 tracking-[0.25px] text-foreground">
        {content && (
          <p className="m-0 whitespace-pre-wrap leading-6">
            {segments.map((segment) =>
              segment.kind === "text" ? (
                <span key={`text-${segment.start}-${segment.end}`}>
                  {segment.text}
                </span>
              ) : (
                <span
                  key={`mention-${segment.start}-${segment.end}`}
                  data-mention-type={segment.type}
                  data-mention-value={segment.value}
                  title={segment.raw}
                  className="inline-flex max-w-[min(100%,360px)] items-baseline gap-1 font-medium whitespace-nowrap text-selection-foreground"
                >
                  <span
                    className="relative top-[2px] ml-1 inline-flex shrink-0 items-center"
                    aria-hidden="true"
                  >
                    <MentionTokenIcon
                      type={segment.type}
                      value={segment.value}
                    />
                  </span>
                  <span className="min-w-0 truncate">
                    {getMentionDisplayLabel(segment.type, segment.value)}
                  </span>
                </span>
              ),
            )}
          </p>
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
  )
}
