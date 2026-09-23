import { useEffect, useRef, useState } from "react"
import { MessagesSquare } from "lucide-react"

import { chatWithKnowledgeBase } from "@/api/knowledge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { useTranslation } from "@/i18n"
import type { KnowledgeCitation } from "@/types/knowledge"

interface ChatMessage {
  role: "user" | "assistant"
  content: string
  citations?: KnowledgeCitation[]
}

export function ChatPanel({ kbId }: { kbId: string }) {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState("")
  const [sending, setSending] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    })
  }, [messages])

  async function handleSend() {
    const query = draft.trim()
    if (!query || sending) return
    setDraft("")
    setMessages((previous) => [...previous, { role: "user", content: query }])
    setSending(true)
    try {
      const response = await chatWithKnowledgeBase(kbId, query)
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: response.answer,
          citations: response.citations,
        },
      ])
    } catch (caught) {
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: caught instanceof Error ? caught.message : t("Request failed"),
        },
      ])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="grid h-full min-h-0 [grid-template-rows:minmax(0,1fr)_auto]">
      <div ref={listRef} className="min-h-0 overflow-y-auto">
        {messages.length ? (
          <ul className="mx-auto grid max-w-3xl gap-4 p-4">
            {messages.map((message, index) => (
              <li
                key={index}
                className={`grid gap-2 ${
                  message.role === "user" ? "justify-items-end" : ""
                }`}
              >
                <div
                  className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm ${
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  }`}
                >
                  {message.content}
                </div>
                {message.citations && message.citations.length > 0 && (
                  <div className="max-w-[85%] rounded-2xl border border-border bg-background px-4 py-3 text-xs text-muted-foreground">
                    <div className="mb-1 font-medium text-foreground">
                      {t("Citations")}
                    </div>
                    <ol className="grid gap-1">
                      {message.citations.map((citation, position) => (
                        <li key={citation.chunk_id}>
                          [{position + 1}] {citation.file_name} —{" "}
                          {citation.excerpt}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <div className="grid h-full place-content-center justify-items-center gap-3 text-muted-foreground">
            <MessagesSquare size={28} />
            <strong className="text-foreground">
              {t("Ask a question")}
            </strong>
          </div>
        )}
      </div>
      <form
        className="border-t border-border p-3"
        onSubmit={(event) => {
          event.preventDefault()
          handleSend()
        }}
      >
        <div className="mx-auto flex max-w-3xl items-center gap-2 rounded-2xl border border-border bg-muted px-3 py-2">
          <Textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
            placeholder={t("Ask a question")}
            aria-label={t("Ask this knowledge base")}
            rows={1}
            className="min-h-0 min-w-0 flex-1 resize-none border-0 bg-transparent px-0 py-0 focus-visible:ring-0"
          />
          <Button
            variant="default"
            type="submit"
            aria-label={t("Send question")}
            disabled={!draft.trim() || sending}
            className="grid size-10 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground disabled:bg-muted disabled:text-muted-foreground"
          >
            {sending ? <Spinner className="size-4" /> : "↑"}
          </Button>
        </div>
      </form>
    </div>
  )
}
