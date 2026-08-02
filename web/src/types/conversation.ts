export type LocalAttachment = {
  id: string
  name: string
  size: number
}

export type LocalMessage = {
  id: string
  role: "user"
  content: string
  createdAt: string
  attachments: LocalAttachment[]
}

export type LocalConversation = {
  id: string
  title: string
  updatedAt: string
  messages: LocalMessage[]
}
