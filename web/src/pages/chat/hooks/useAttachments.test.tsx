import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { useAttachments } from "@/pages/chat/hooks/useAttachments";
import type { UploadedAttachmentResponse } from "@/api/attachment";

const mocks = vi.hoisted(() => ({ upload: vi.fn() }));
vi.mock("@/api/attachment", () => ({
  uploadChatAttachments: mocks.upload,
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const attachment = (name: string): UploadedAttachmentResponse => ({
  file_id: `file-${name}`,
  file_name: `${name}.txt`,
  content_type: "text/plain",
  file_size: 12,
  bucket_name: "attachments",
  object_name: `${name}.txt`,
  access_url: `/files/file-${name}`,
});

it("manages the attachment collection, upload count and error independently", () => {
  const { result } = renderHook(() => useAttachments());
  const first = attachment("first");
  const second = attachment("second");

  act(() => {
    result.current.setAttachments([first]);
    result.current.addAttachments([second]);
    result.current.removeAttachment(first.file_id);
    result.current.beginAttachmentUpload(2);
    result.current.beginAttachmentUpload(1);
    result.current.setAttachmentError("Upload failed");
  });
  expect(result.current.state).toEqual({
    attachments: [second],
    uploadingCount: 3,
    uploadError: "Upload failed",
  });

  act(() => {
    result.current.finishAttachmentUpload(2);
    expect(result.current.getState().uploadingCount).toBe(1);
    result.current.finishAttachmentUpload(10);
    result.current.clearAttachmentError();
    result.current.clearAttachments();
  });
  expect(result.current.state).toEqual({
    attachments: [],
    uploadingCount: 0,
    uploadError: "",
  });

  act(() => {
    result.current.beginAttachmentUpload(2);
    result.current.resetAttachmentUpload();
  });
  expect(result.current.state.uploadingCount).toBe(0);
});

it("uploads files and appends the response to the latest collection", async () => {
  const { result } = renderHook(() => useAttachments());
  const existing = attachment("existing");
  const uploaded = attachment("uploaded");
  let resolveUpload!: (value: UploadedAttachmentResponse[]) => void;
  mocks.upload.mockReturnValue(
    new Promise<UploadedAttachmentResponse[]>((resolve) => {
      resolveUpload = resolve;
    }),
  );
  const files = [
    new File(["one"], "one.txt", { type: "text/plain" }),
    new File(["two"], "two.txt", { type: "text/plain" }),
  ];
  let pending!: Promise<UploadedAttachmentResponse[] | null>;

  act(() => {
    result.current.setAttachments([existing]);
    result.current.setAttachmentError("Old error");
    pending = result.current.uploadFiles(files);
  });
  expect(result.current.state).toMatchObject({
    attachments: [existing],
    uploadingCount: 2,
    uploadError: "",
  });

  await act(async () => {
    resolveUpload([uploaded]);
    await pending;
  });
  expect(mocks.upload).toHaveBeenCalledWith(files);
  expect(result.current.state).toEqual({
    attachments: [existing, uploaded],
    uploadingCount: 0,
    uploadError: "",
  });
});

it("stores a mapped upload error and releases the pending count", async () => {
  const failure = new Error("network unavailable");
  mocks.upload.mockRejectedValue(failure);
  const errorText = vi.fn(() => "Upload failed");
  const { result } = renderHook(() => useAttachments(errorText));

  let uploaded: UploadedAttachmentResponse[] | null = [];
  await act(async () => {
    uploaded = await result.current.uploadFiles([
      new File(["one"], "one.txt", { type: "text/plain" }),
    ]);
  });

  expect(uploaded).toBeNull();
  expect(errorText).toHaveBeenCalledWith(failure);
  expect(result.current.state).toEqual({
    attachments: [],
    uploadingCount: 0,
    uploadError: "Upload failed",
  });
});

it("ignores stale upload results after invalidation and fully resets state", async () => {
  const { result } = renderHook(() => useAttachments());
  const existing = attachment("existing");
  let resolveUpload!: (value: UploadedAttachmentResponse[]) => void;
  mocks.upload.mockReturnValue(
    new Promise<UploadedAttachmentResponse[]>((resolve) => {
      resolveUpload = resolve;
    }),
  );
  let pending!: Promise<UploadedAttachmentResponse[] | null>;

  act(() => {
    result.current.setAttachments([existing]);
    result.current.setAttachmentError("Keep this until reset");
    pending = result.current.uploadFiles([
      new File(["one"], "one.txt", { type: "text/plain" }),
    ]);
  });
  act(() => result.current.invalidate());
  expect(result.current.state).toEqual({
    attachments: [existing],
    uploadingCount: 0,
    uploadError: "",
  });

  await act(async () => {
    resolveUpload([attachment("stale")]);
    expect(await pending).toBeNull();
  });
  expect(result.current.state.attachments).toEqual([existing]);

  act(() => result.current.reset());
  expect(result.current.state).toEqual({
    attachments: [],
    uploadingCount: 0,
    uploadError: "",
  });
});
