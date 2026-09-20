import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type {
  ClipboardEvent,
  DragEvent,
  KeyboardEvent,
  SubmitEvent,
} from "react";
import {
  ArrowUpIcon,
  LoaderCircleIcon,
  MicIcon,
  PaperclipIcon,
  PlusIcon,
  SquareIcon,
} from "lucide-react";
import { createShader, playSweep, accentChain, ACCENTS } from "glimm";

const RAINBOW = accentChain([
  ACCENTS.red,
  ACCENTS.orange,
  ACCENTS.yellow,
  ACCENTS.green,
  ACCENTS.cyan,
  ACCENTS.blue,
  ACCENTS.purple,
]);

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useTranslation } from "@/i18n";
import { Attachment } from "@/pages/chat/components/Attachment";
import ModelSelector from "@/pages/chat/components/ModelSelector";
import type { UploadedAttachmentResponse } from "@/types/attachment";
import type { ChatModelOption } from "@/types/model";

type AgentMessageComposerProps = {
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
};

type SpeechRecognitionResultLike = {
  0: { transcript: string };
  length: number;
};

type SpeechRecognitionEventLike = {
  results: ArrayLike<SpeechRecognitionResultLike>;
};

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;
type SpeechRecognitionWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

const COMPOSER_MIN_HEIGHT = 40;
const COMPOSER_MAX_HEIGHT = 160;
const CONTROL_MOTION_DURATION = 240;

export function AgentMessageComposer({
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
}: AgentMessageComposerProps) {
  const { t } = useTranslation();
  const composer = useRef<HTMLFormElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const editor = useRef<HTMLTextAreaElement>(null);
  const controls = useRef<HTMLDivElement>(null);
  const previousPositions = useRef(new Map<string, DOMRect>());
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const dictationBase = useRef("");
  const setDraftRef = useRef(setDraft);
  const [composing, setComposing] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [speechSupported, setSpeechSupported] = useState<boolean | null>(null);
  const [listening, setListening] = useState(false);
  const [modelSweep, setModelSweep] = useState(0);
  const glimmRef = useRef<HTMLCanvasElement>(null);
  const shaderRef = useRef<ReturnType<typeof createShader> | null>(null);
  const sweepingRef = useRef(false);

  const makeShader = () => {
    const canvas = glimmRef.current;
    if (!canvas) return null;
    const random = Math.random;
    Math.random = () => 0;
    try {
      return createShader({
        canvas,
        palette: RAINBOW,
        direction: "ltr",
        bandTight: 10,
        swellAmount: 0.85,
      });
    } finally {
      Math.random = random;
    }
  };

  useEffect(() => {
    shaderRef.current = makeShader();
    return () => {
      shaderRef.current?.destroy();
      shaderRef.current = null;
    };
  }, []);

  const celebrate = () => {
    if (sweepingRef.current) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    shaderRef.current?.destroy();
    const shader = makeShader();
    shaderRef.current = shader;
    if (!shader) return;
    sweepingRef.current = true;
    const sweep = playSweep(shader, {
      palette: RAINBOW,
      direction: "ltr",
      sweepMs: 570,
      outroMs: 80,
      peakAlpha: 1.3,
      bandTight: 10,
      brightness: 1.4,
      swellAmount: 1,
      waveSpeed: 1.8,
      easing: "easeOutExpo",
    });
    sweep.done.finally(() => {
      sweepingRef.current = false;
    });
  };

  setDraftRef.current = setDraft;

  const actionDisabled =
    disabled ||
    (!running &&
      (uploading > 0 || (!draft.trim() && attachments.length === 0)));

  useEffect(() => {
    const speechWindow = window as SpeechRecognitionWindow;
    const Recognition =
      speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setSpeechSupported(false);
      return;
    }

    const instance = new Recognition();
    instance.continuous = false;
    instance.interimResults = true;
    instance.lang = document.documentElement.lang || navigator.language;
    instance.onresult = (event) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index]?.[0]?.transcript || "";
      }
      const base = dictationBase.current.trimEnd();
      const spoken = transcript.trim();
      setDraftRef.current(`${base}${base && spoken ? " " : ""}${spoken}`);
    };
    instance.onend = () => setListening(false);
    instance.onerror = () => setListening(false);
    recognition.current = instance;
    setSpeechSupported(true);

    return () => {
      instance.abort();
      recognition.current = null;
    };
  }, []);

  useEffect(() => {
    if ((disabled || running) && listening) {
      recognition.current?.stop();
      setListening(false);
    }
  }, [disabled, listening, running]);

  useLayoutEffect(() => {
    const textarea = editor.current;
    if (!textarea) return;

    textarea.style.height = "0px";
    const contentHeight = textarea.scrollHeight;
    const nextHeight = Math.min(
      COMPOSER_MAX_HEIGHT,
      Math.max(COMPOSER_MIN_HEIGHT, contentHeight),
    );
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY =
      contentHeight > COMPOSER_MAX_HEIGHT ? "auto" : "hidden";

    const nextExpanded =
      draft.includes("\n") || contentHeight > COMPOSER_MIN_HEIGHT + 8;
    setExpanded((current) =>
      current === nextExpanded ? current : nextExpanded,
    );
  }, [draft]);

  useLayoutEffect(() => {
    const container = controls.current;
    if (!container) return;

    const reduceMotion =
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const nextPositions = new Map<string, DOMRect>();

    container
      .querySelectorAll<HTMLElement>("[data-composer-control]")
      .forEach((element) => {
        const key = element.dataset.composerControl;
        if (!key) return;

        const next = element.getBoundingClientRect();
        const previous = previousPositions.current.get(key);
        nextPositions.set(key, next);

        if (!previous || reduceMotion || typeof element.animate !== "function") {
          return;
        }

        const deltaX = previous.left - next.left;
        const deltaY = previous.top - next.top;
        if (deltaX === 0 && deltaY === 0) return;

        element.animate(
          [
            { transform: `translate(${deltaX}px, ${deltaY}px)` },
            { transform: "translate(0, 0)" },
          ],
          {
            duration: CONTROL_MOTION_DURATION,
            easing: "cubic-bezier(0.22, 1, 0.36, 1)",
          },
        );
      });

    previousPositions.current = nextPositions;
  }, [expanded]);

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

  const stopDictation = () => {
    if (!listening) return;
    recognition.current?.stop();
    setListening(false);
  };

  const submitMessage = () => {
    stopDictation();
    submit();
  };

  const toggleDictation = () => {
    const instance = recognition.current;
    if (!instance) return;
    if (listening) {
      stopDictation();
      return;
    }

    dictationBase.current = draft;
    try {
      instance.start();
      setListening(true);
    } catch {
      setListening(false);
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
      if (!actionDisabled && !running) submitMessage();
    }
  };

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!actionDisabled && !running) submitMessage();
  };

  const onSelectModel = (id: string) => {
    if (id !== modelId) {
      setModelSweep((current) => current + 1);
      celebrate();
    }
    selectModel(id);
  };

  const dictationLabel = speechSupported
    ? listening
      ? t("Stop dictation")
      : t("Start dictation")
    : t("Dictation is not supported in this browser");

  return (
    <form
      ref={composer}
      aria-label={t("Agent message composer")}
      aria-busy={uploading > 0}
      data-expanded={expanded}
      className="relative isolate flex w-full flex-col overflow-hidden rounded-3xl border border-border bg-card p-2 shadow-sm transition-[border-color,box-shadow] focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/20"
      onSubmit={onSubmit}
      onDragOver={(event) => event.preventDefault()}
      onDrop={onDrop}
      onPaste={onPaste}
    >
      <canvas
        ref={glimmRef}
        aria-hidden="true"
        data-model-sweep={modelSweep > 0 ? "" : undefined}
        className="pointer-events-none absolute inset-0 -z-10 h-full w-full"
        style={{ borderRadius: "inherit" }}
      />

      {(attachments.length > 0 || uploading > 0) && (
        <ul className="relative z-10 m-0 flex w-full list-none flex-wrap gap-1.5 px-1 pb-2">
          {attachments.map((item) => (
            <Attachment
              key={item.file_id}
              attachment={item}
              remove={removeAttachment}
            />
          ))}
          {uploading > 0 && (
            <li
              className="flex h-9 items-center gap-2 rounded-full bg-muted px-3 text-xs text-muted-foreground motion-safe:animate-in motion-safe:fade-in motion-safe:zoom-in-95 motion-safe:duration-200"
              role="status"
            >
              <LoaderCircleIcon className="size-3.5 animate-spin motion-reduce:animate-none" />
              {uploading > 1
                ? t("Uploading {{files}} files…", { files: uploading })
                : t("Uploading…")}
            </li>
          )}
        </ul>
      )}

      <div
        ref={controls}
        className={`relative z-10 grid w-full items-end gap-x-1.5 gap-y-1 ${
          expanded
            ? "grid-cols-[2.5rem_auto_minmax(0,1fr)_2.5rem_2.5rem]"
            : "grid-cols-[2.5rem_minmax(0,1fr)_auto_2.5rem_2.5rem]"
        }`}
      >
        <Input
          ref={fileInput}
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
            render={<Button variant="ghost" size="icon-lg" />}
            type="button"
            disabled={disabled}
            aria-label={t("Action menu")}
            data-composer-control="actions"
            className={`rounded-xl bg-muted/70 text-muted-foreground transition-transform duration-150 hover:text-foreground active:scale-[0.94] motion-reduce:transform-none ${
              expanded ? "col-start-1 row-start-2" : "col-start-1 row-start-1"
            }`}
          >
            <PlusIcon className="transition-transform duration-200 group-aria-expanded/button:rotate-45 motion-reduce:transition-none" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            anchor={composer}
            side={placement}
            align="start"
            aria-label={t("Actions menu")}
          >
            <DropdownMenuItem onClick={() => fileInput.current?.click()}>
              <PaperclipIcon />
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
          placeholder={listening ? t("Listening…") : t("Ask anything")}
          rows={1}
          className={`max-h-40 min-h-10 min-w-0 resize-none border-0 bg-transparent px-2 py-2 text-base leading-6 shadow-none transition-[height] duration-200 ease-out focus-visible:border-transparent focus-visible:ring-0 disabled:bg-transparent disabled:opacity-60 motion-reduce:transition-none md:text-sm ${
            expanded
              ? "col-span-full col-start-1 row-start-1"
              : "col-start-2 row-start-1"
          }`}
        />

        <div
          data-composer-control="model"
          className={
            expanded
              ? "col-start-2 row-start-2 min-w-0 justify-self-start"
              : "col-start-3 row-start-1 min-w-0"
          }
        >
          <ModelSelector
            models={models}
            selectedId={modelId}
            loading={modelsLoading}
            disabled={disabled || running}
            placement={placement}
            select={onSelectModel}
          />
        </div>

        <Tooltip>
          <TooltipTrigger
            render={<Button variant="ghost" size="icon-lg" />}
            type="button"
            disabled={disabled || running || speechSupported !== true}
            aria-label={dictationLabel}
            aria-pressed={listening}
            data-composer-control="dictation"
            onClick={toggleDictation}
            className={`rounded-xl text-muted-foreground transition-transform duration-150 hover:bg-muted hover:text-foreground active:scale-[0.94] motion-reduce:transform-none ${
              expanded ? "col-start-4 row-start-2" : "col-start-4 row-start-1"
            }`}
          >
            {listening ? (
              <span className="flex h-4 items-center gap-0.5" aria-hidden="true">
                <span className="agent-composer-wave-bar" />
                <span className="agent-composer-wave-bar" />
                <span className="agent-composer-wave-bar" />
              </span>
            ) : (
              <MicIcon />
            )}
          </TooltipTrigger>
          <TooltipContent>{dictationLabel}</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                variant={running ? "secondary" : "default"}
                size="icon-lg"
              />
            }
            type="button"
            disabled={actionDisabled}
            aria-label={running ? t("Cancel response") : t("Send message")}
            data-composer-control="submit"
            onClick={running ? cancel : submitMessage}
            className={`rounded-xl transition-transform duration-150 active:scale-[0.94] motion-reduce:transform-none ${
              expanded ? "col-start-5 row-start-2" : "col-start-5 row-start-1"
            }`}
          >
            {running ? (
              <SquareIcon className="size-3.5" fill="currentColor" />
            ) : (
              <ArrowUpIcon />
            )}
          </TooltipTrigger>
          <TooltipContent>{running ? t("Cancel") : t("Send")}</TooltipContent>
        </Tooltip>
      </div>
    </form>
  );
}
