import { useCallback, useRef, useState } from "react";

import { useChatMessages } from "@/pages/chat/hooks/useChatMessages";
import type { UploadedAttachmentResponse } from "@/types/attachment";
import type {
  ThreadDetailResponse,
  ThreadResponse,
  ThreadSummaryResponse,
} from "@/types/chat";

interface ChatState {
  thread: ThreadSummaryResponse | null;
  draft: string;
  attachments: UploadedAttachmentResponse[];
  uploadingCount: number;
  uploadError: string;
  loading: boolean;
  submitting: boolean;
  error: string;
}

export interface ChatSubmission {
  query: string;
  draft: string;
  attachments: UploadedAttachmentResponse[];
  optimisticMessageId: number;
}

const initialState = (): ChatState => ({
  thread: null,
  draft: "",
  attachments: [],
  uploadingCount: 0,
  uploadError: "",
  loading: false,
  submitting: false,
  error: "",
});

export function useChat() {
  const [state, setState] = useState<ChatState>(initialState);
  const current = useRef(state);
  const chatMessages = useChatMessages();
  const { getMessages } = chatMessages;

  // Stream callbacks need the latest state while an earlier request is awaiting.
  const getState = useCallback(
    () => ({ ...current.current, messages: getMessages() }),
    [getMessages],
  );
  const update = useCallback(
    (
      change:
        Partial<ChatState> | ((previous: ChatState) => Partial<ChatState>),
    ) => {
      const patch =
        typeof change === "function" ? change(current.current) : change;
      const next = { ...current.current, ...patch };
      current.current = next;
      setState(next);
    },
    [],
  );

  function clearPendingInput() {
    update({ draft: "", attachments: [], uploadingCount: 0, uploadError: "" });
  }

  function applyThreadDetail(detail: ThreadDetailResponse) {
    chatMessages.applyHistory(detail.messages);
    update({ thread: detail.thread });
  }

  function applyCreatedThread(created: ThreadResponse): ThreadSummaryResponse {
    const thread: ThreadSummaryResponse = {
      thread_id: created.thread_id,
      title: created.title,
      summary: null,
      agent_id: created.agent_id,
      metadata: created.metadata,
      created_at: created.created_at,
      updated_at: created.updated_at,
      last_message_at: null,
    };
    update({ thread });
    return thread;
  }

  function beginSubmission(): ChatSubmission | null {
    const snapshot = getState();
    const query = snapshot.draft.trim();
    const attachments = [...snapshot.attachments];
    if (
      (!query && attachments.length === 0) ||
      snapshot.uploadingCount > 0 ||
      snapshot.submitting
    )
      return null;
    const createdAt = new Date().toISOString();
    const optimisticMessageId = chatMessages.addOptimisticMessage({
      role: "user",
      content: query,
      image_content: null,
      message_type: attachments.length
        ? query
          ? "multimodal"
          : "attachment"
        : "text",
      status: "pending",
      request_id: null,
      run: null,
      attachments: attachments.map((attachment) => ({
        file_id: attachment.file_id,
        file_name: attachment.file_name,
        content_type: attachment.content_type,
        file_size: attachment.file_size,
        available: true,
        access_url: attachment.access_url,
      })),
      created_at: createdAt,
      updated_at: createdAt,
    });
    update({
      draft: "",
      attachments: [],
      uploadError: "",
      submitting: true,
      error: "",
    });
    return {
      query,
      draft: snapshot.draft,
      attachments,
      optimisticMessageId,
    };
  }

  function rollbackSubmission(submission: ChatSubmission) {
    chatMessages.removeOptimisticMessage(submission.optimisticMessageId);
    update({ draft: submission.draft, attachments: submission.attachments });
  }

  function appendUploadedAttachments(uploaded: UploadedAttachmentResponse[]) {
    update((previous) => ({
      attachments: [...previous.attachments, ...uploaded],
    }));
  }

  function removeAttachment(fileId: string) {
    update((previous) => ({
      attachments: previous.attachments.filter(
        (attachment) => attachment.file_id !== fileId,
      ),
    }));
  }

  function resetThread() {
    chatMessages.clearMessages();
    update(initialState());
  }

  return {
    state: { ...state, messages: chatMessages.messages },
    getState,
    update,
    clearPendingInput,
    applyThreadDetail,
    applyCreatedThread,
    clearRunStreamMessages: chatMessages.clearRunStreamMessages,
    applyRunMessageEvent: chatMessages.applyRunMessageEvent,
    flushStream: chatMessages.flushStream,
    resetStream: chatMessages.resetStream,
    clearMessages: chatMessages.clearMessages,
    beginSubmission,
    rollbackSubmission,
    appendUploadedAttachments,
    removeAttachment,
    resetThread,
  };
}
