import { buildChatRenderItems } from "@/pages/chat/chat-render-items"
import type { ChatMessage as Message } from "@/pages/chat/types"
import { ChatMessage } from "./ChatMessage"

interface Props {
  messages: Message[]
  threadId: string | undefined
  currentRunId: string | null
  status: string | null
  active: boolean
  waiting: boolean
  startedAt?: number | null
}

export function ConversationMessages(props: Props) {
  const items = buildChatRenderItems(props.messages, {
    threadId: props.threadId,
    currentRunId: props.currentRunId,
    status: props.status,
    active: props.active,
    waiting: props.waiting,
    startedAt: props.startedAt,
  })

  return items.map((item) => <ChatMessage key={item.key} item={item} />)
}
