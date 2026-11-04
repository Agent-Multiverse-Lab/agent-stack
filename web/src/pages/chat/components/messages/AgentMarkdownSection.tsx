import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import type { ThreadMessageAttachmentResponse } from "@/api/attachment"
import { Attachment } from "@/pages/chat/components/Attachment"

interface AgentMarkdownSectionProps {
  content: string
  attachments?: ThreadMessageAttachmentResponse[]
  className?: string
}

export function AgentMarkdownSection({
  content,
  attachments = [],
  className = "min-w-0 max-w-full text-sm leading-6 tracking-[0.25px] text-foreground",
}: AgentMarkdownSectionProps) {
  if (!content && attachments.length === 0) return null

  return (
    <article className={className}>
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
  )
}
