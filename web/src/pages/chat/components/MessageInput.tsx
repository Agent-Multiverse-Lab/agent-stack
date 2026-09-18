import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useRef, useState } from "react";
import type { ClipboardEvent, DragEvent, KeyboardEvent, SubmitEvent } from "react";
import { ArrowUp, Paperclip, Plus, Square } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { UploadedAttachmentResponse } from "@/types/attachment";
import type { ChatModelOption } from "@/types/model";
import { Attachment } from "@/pages/chat/components/Attachment";
import ModelSelector from "@/pages/chat/components/ModelSelector";
import { useTranslation } from "@/i18n";

export function MessageInput({
  draft,
  setDraft,
  attachments,
  uploading,
  running,
  disabled,
  modelId,
  models,
  modelsLoading,
  placement,
  selectModel,
  upload,
  removeAttachment,
  submit,
  cancel,
}: {
  draft: string;
  setDraft: (value: string) => void;
  attachments: UploadedAttachmentResponse[];
  uploading: number;
  running: boolean;
  disabled: boolean;
  modelId: string;
  models: ChatModelOption[];
  modelsLoading: boolean;
  placement: "top" | "bottom";
  selectModel: (id: string) => void;
  upload: (files: File[]) => void;
  removeAttachment: (id: string) => void;
  submit: () => void;
  cancel: () => void;
}) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  const editor = useRef<HTMLTextAreaElement>(null);
  const [composing, setComposing] = useState(false);
  const actionDisabled =
    disabled ||
    (!running &&
      (uploading > 0 || (!draft.trim() && attachments.length === 0)));
  const selectFiles = (files: FileList | null) => {
    if (files?.length) upload(Array.from(files));
  };
  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    if (!disabled) selectFiles(event.dataTransfer.files);
  };
  const onPaste = (event: ClipboardEvent) => {
    if (!disabled && event.clipboardData.files.length) {
      event.preventDefault();
      selectFiles(event.clipboardData.files);
    }
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing &&
      !composing
    ) {
      event.preventDefault();
      if (!actionDisabled && !running) submit();
    }
  };
  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!actionDisabled && !running) submit();
  };
  return (
    <form
      className="relative flex w-full flex-col rounded-[1.7rem] border border-graphite/14 bg-paper p-2 shadow-[0_10px_28px_rgba(13,13,13,0.07)] focus-within:border-graphite/24"
      onSubmit={onSubmit}
      onDragOver={(event) => event.preventDefault()}
      onDrop={onDrop}
      onPaste={onPaste}
    >
      {(attachments.length > 0 || uploading > 0) && (
        <ul className="m-0 flex w-full list-none flex-wrap gap-2 px-3 py-2.5">
          {attachments.map((item) => (
            <Attachment
              key={item.file_id}
              attachment={item}
              remove={removeAttachment}
            />
          ))}
          {uploading > 0 && (
            <li
              className="flex h-11 items-center rounded-full bg-mist px-4 text-sm text-slate"
              role="status"
            >
              {uploading > 1
                ? t("Uploading {{files}} files…", { files: uploading })
                : t("Uploading…")}
            </li>
          )}
        </ul>
      )}
      <div className="flex w-full items-end gap-2">
        <Input
          ref={input}
          className="hidden"
          type="file"
          multiple
          tabIndex={-1}
          onChange={(event) => {
            selectFiles(event.target.files);
            event.target.value = "";
          }}
        />
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button variant="ghost" />}
            type="button"
            disabled={disabled}
            aria-label={t("Action menu")}
            className="grid size-10 place-items-center rounded-full bg-graphite/6 disabled:opacity-40"
          >
            <Plus size={19} />
          </DropdownMenuTrigger>
          <DropdownMenuContent side={placement} className="w-48 p-2" aria-label={t("Actions menu")}>
            <DropdownMenuItem onClick={() => input.current?.click()}>
              <Paperclip size={18} />
              {t("Add attachment")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Textarea
          ref={editor}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          onCompositionStart={() => setComposing(true)}
          onCompositionEnd={() => setComposing(false)}
          disabled={disabled}
          aria-label={t("Message")}
          placeholder={t("Ask anything")}
          rows={1}
          className="min-h-10 max-h-[180px] min-w-0 flex-1 resize-none overflow-y-auto border-0 bg-transparent px-2 py-2 text-[0.95rem] leading-6 focus-visible:ring-0 disabled:opacity-60"
          style={{
            height: Math.min(
              180,
              Math.max(40, draft.split("\n").length * 24 + 16),
            ),
          }}
        />
        <ModelSelector
          models={models}
          selectedId={modelId}
          loading={modelsLoading}
          disabled={disabled || running}
          placement={placement}
          select={selectModel}
        />
        <Tooltip>
          <TooltipTrigger
            type="button"
            disabled={actionDisabled}
            aria-label={running ? t("Cancel response") : t("Send message")}
            onClick={running ? cancel : submit}
            className="grid size-10 shrink-0 place-items-center rounded-full bg-graphite text-paper disabled:bg-graphite/18"
          >
            {running ? (
              <Square size={14} fill="currentColor" />
            ) : (
              <ArrowUp size={19} />
            )}
          </TooltipTrigger>
          <TooltipContent>{running ? t("Cancel") : t("Send")}</TooltipContent>
        </Tooltip>
      </div>
    </form>
  );
}
