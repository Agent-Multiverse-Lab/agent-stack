import { useEffect, useRef, useState } from "react"
import { ArrowUp, ArrowUpRight, BookOpen, FileText, MessagesSquare } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

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
  const [error, setError] = useState("")
  const [failedQuery, setFailedQuery] = useState("")
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const sendingRef = useRef(false)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "instant" })
  }, [messages, sending, error])

  async function handleSend(retryQuery?: string) {
    const query = retryQuery || draft.trim()
    if (!query || sendingRef.current) return
    sendingRef.current = true
    setSending(true)
    setError("")
    if (!retryQuery) {
      setDraft("")
      setMessages((previous) => [...previous, { role: "user", content: query }])
    }
    try {
      const response = await chatWithKnowledgeBase(kbId, query)
      setMessages((previous) => [...previous, { role: "assistant", content: response.answer, citations: response.citations }])
      setFailedQuery("")
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("Request failed"))
      setFailedQuery(query)
    } finally { sendingRef.current = false; setSending(false) }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto">
        {messages.length ? (
          <div className="mx-auto max-w-3xl px-6 py-8">
            <ul className="grid gap-7" aria-live="polite" aria-busy={sending}>
              {messages.map((message, index) => (
                <li key={index} className={`grid gap-3 ${message.role === "user" ? "justify-items-end" : ""}`}>
                  {message.role === "assistant" && <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground"><BookOpen className="size-4 text-primary" />{t("Knowledge Chat")}</div>}
                  {message.role === "user" ? <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-message px-4 py-3 text-sm leading-6 text-foreground">{message.content}</div> : <div className="chat-markdown min-w-0 text-sm leading-7 text-foreground"><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown></div>}
                  {message.citations && message.citations.length > 0 && <div className="mt-1 border-t border-border pt-3 text-xs text-muted-foreground"><div className="mb-3 font-medium text-foreground">{t("Citations")}</div><ol className="grid gap-2">{message.citations.map((citation, position) => <li key={`${citation.chunk_id}-${position}`} className="rounded-lg bg-muted/60 px-3 py-3"><div className="mb-1.5 flex items-center gap-2 font-medium text-foreground"><FileText className="size-3.5 shrink-0 text-primary" /><span className="min-w-0 truncate">[{position + 1}] {citation.file_name}</span></div><p className="leading-5">{citation.excerpt}</p></li>)}</ol></div>}
                </li>
              ))}
            </ul>
            {sending && <div role="status" className="mt-7 flex items-center gap-2 text-xs text-muted-foreground"><Spinner className="size-3.5" />{t("Searching your documents…")}</div>}
            {error && <div role="alert" className="mt-5 flex items-center justify-between gap-4 rounded-lg bg-destructive-muted px-4 py-3 text-sm text-destructive"><span>{error}</span><Button variant="outline" size="sm" onClick={() => handleSend(failedQuery)} disabled={sending}>{t("Retry")}</Button></div>}
          </div>
        ) : (
          <div className="mx-auto flex h-full min-h-72 max-w-2xl flex-col items-center justify-center px-6 py-8 text-center">
            <div className="mb-6 grid size-16 place-items-center rounded-2xl bg-selection text-selection-foreground"><MessagesSquare className="size-7" strokeWidth={1.4} /></div>
            <h2 className="text-2xl font-medium tracking-tight">{t("Ask your collection")}</h2>
            <div className="mt-7 flex flex-wrap justify-center gap-2">
              {["Summarize the main topics", "Find the key connections"].map((prompt) => <Button key={prompt} variant="outline" className="h-auto gap-3 py-2.5 text-xs" onClick={() => { setDraft(t(prompt)); inputRef.current?.focus() }}>{t(prompt)}<ArrowUpRight className="size-3.5" /></Button>)}
            </div>
          </div>
        )}
      </div>
      <form className="shrink-0 px-6 pb-6 pt-3" onSubmit={(event) => { event.preventDefault(); handleSend() }}>
        <div className="mx-auto max-w-3xl rounded-xl border border-input bg-card px-4 pb-3 pt-4">
          <Textarea ref={inputRef} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() }
          }} placeholder={t("Ask a question about your documents…")} aria-label={t("Ask this knowledge base")} rows={2} className="min-h-12 resize-none border-0 bg-transparent p-0" />
          <div className="mt-3 flex items-center justify-between gap-3"><span className="flex items-center gap-1.5 text-[10px] text-muted-foreground"><BookOpen className="size-3" />{t("This collection only")}</span><Button type="submit" aria-label={t("Send question")} disabled={!draft.trim() || sending} size="icon">{sending ? <Spinner /> : <ArrowUp />}</Button></div>
        </div>
      </form>
    </div>
  )
}
