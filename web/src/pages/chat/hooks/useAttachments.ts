import { useCallback, useRef, useState } from "react";

import { uploadChatAttachments } from "@/api/attachment";
import type { UploadedAttachmentResponse } from "@/api/attachment";

export interface AttachmentsState {
  attachments: UploadedAttachmentResponse[];
  uploadingCount: number;
  uploadError: string;
}

type AttachmentsStateUpdater = (
  previous: AttachmentsState,
) => AttachmentsState;

const initialState = (): AttachmentsState => ({
  attachments: [],
  uploadingCount: 0,
  uploadError: "",
});

const defaultErrorText = (caught: unknown) =>
  caught instanceof Error ? caught.message : "Request failed";

/** Owns draft attachments and the /api/chat/attachment upload lifecycle. */
export function useAttachments(
  errorText: (caught: unknown) => string = defaultErrorText,
) {
  const [state, setState] = useState<AttachmentsState>(initialState);
  const current = useRef(state);
  const generation = useRef(0);

  const getState = useCallback(() => current.current, []);
  const update = useCallback((updater: AttachmentsStateUpdater) => {
    const next = updater(current.current);
    current.current = next;
    setState(next);
  }, []);

  const setAttachments = useCallback(
    (attachments: UploadedAttachmentResponse[]) => {
      update((previous) => ({ ...previous, attachments }));
    },
    [update],
  );

  const addAttachments = useCallback(
    (uploaded: UploadedAttachmentResponse[]) => {
      update((previous) => ({
        ...previous,
        attachments: [...previous.attachments, ...uploaded],
      }));
    },
    [update],
  );

  const removeAttachment = useCallback(
    (fileId: string) => {
      update((previous) => ({
        ...previous,
        attachments: previous.attachments.filter(
          (attachment) => attachment.file_id !== fileId,
        ),
      }));
    },
    [update],
  );

  const clearAttachments = useCallback(() => {
    update((previous) => ({ ...previous, attachments: [] }));
  }, [update]);

  const beginAttachmentUpload = useCallback(
    (fileCount: number) => {
      if (fileCount <= 0) return;
      update((previous) => ({
        ...previous,
        uploadingCount: previous.uploadingCount + fileCount,
      }));
    },
    [update],
  );

  const finishAttachmentUpload = useCallback(
    (fileCount: number) => {
      if (fileCount <= 0) return;
      update((previous) => ({
        ...previous,
        uploadingCount: Math.max(0, previous.uploadingCount - fileCount),
      }));
    },
    [update],
  );

  const resetAttachmentUpload = useCallback(() => {
    update((previous) => ({ ...previous, uploadingCount: 0 }));
  }, [update]);

  const setAttachmentError = useCallback(
    (uploadError: string) => {
      update((previous) => ({ ...previous, uploadError }));
    },
    [update],
  );

  const clearAttachmentError = useCallback(() => {
    update((previous) => ({ ...previous, uploadError: "" }));
  }, [update]);

  const uploadFiles = useCallback(
    async (files: File[]): Promise<UploadedAttachmentResponse[] | null> => {
      if (!files.length) return [];
      const expected = generation.current;
      update((previous) => ({
        ...previous,
        uploadingCount: previous.uploadingCount + files.length,
        uploadError: "",
      }));
      try {
        const uploaded = await uploadChatAttachments(files);
        if (generation.current !== expected) return null;
        update((previous) => ({
          ...previous,
          attachments: [...previous.attachments, ...uploaded],
          uploadingCount: Math.max(
            0,
            previous.uploadingCount - files.length,
          ),
        }));
        return uploaded;
      } catch (caught) {
        if (generation.current !== expected) return null;
        update((previous) => ({
          ...previous,
          uploadingCount: Math.max(
            0,
            previous.uploadingCount - files.length,
          ),
          uploadError: errorText(caught),
        }));
        return null;
      }
    },
    [errorText, update],
  );

  const invalidate = useCallback(() => {
    generation.current += 1;
    update((previous) => ({ ...previous, uploadingCount: 0 }));
  }, [update]);

  const reset = useCallback(() => {
    generation.current += 1;
    update(() => initialState());
  }, [update]);

  return {
    state,
    getState,
    uploadFiles,
    setAttachments,
    addAttachments,
    removeAttachment,
    clearAttachments,
    beginAttachmentUpload,
    finishAttachmentUpload,
    resetAttachmentUpload,
    setAttachmentError,
    clearAttachmentError,
    invalidate,
    reset,
  };
}
