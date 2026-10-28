import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type {
  ChangeEvent,
  ClipboardEvent,
  DragEvent,
  KeyboardEvent,
  SubmitEvent,
} from "react";
import {
  ArrowUpIcon,
  BookOpenIcon,
  BotIcon,
  FileTextIcon,
  FolderIcon,
  LoaderCircleIcon,
  MicIcon,
  PaperclipIcon,
  PlugIcon,
  PlusIcon,
  SquareIcon,
  WandSparklesIcon,
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

import { listAgents } from "@/api/agent";
import type { UploadedAttachmentResponse } from "@/api/attachment";
import { listKnowledgeBases } from "@/api/knowledge";
import { listSandboxWorkspace } from "@/api/sandbox";
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
import {
  expandMentionDeletionRange,
  findActiveMentionQuery,
  formatMentionToken,
  replaceRawRange,
  splitTextByQuery,
  type MentionItem,
  type MentionSources,
} from "@/pages/chat/mentions";
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
  threadId?: string;
  mention?: MentionSources;
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

const COMPOSER_MIN_HEIGHT = 44;
const COMPOSER_MAX_HEIGHT = 200;
const CONTROL_MOTION_DURATION = 240;

function HighlightedText({
  text,
  query,
}: {
  text: string;
  query: string;
}) {
  const parts = splitTextByQuery(text, query);
  return (
    <>
      {parts.map((part, index) => (
        <span
          key={`${part.text}-${index}`}
          className={part.isMatch ? "font-semibold text-primary" : undefined}
        >
          {part.text}
        </span>
      ))}
    </>
  );
}

function MentionItemIcon({ item }: { item: MentionItem }) {
  if (item.type === "file") {
    return item.isDir ? (
      <FolderIcon className="size-4 shrink-0 text-muted-foreground" />
    ) : (
      <FileTextIcon className="size-4 shrink-0 text-muted-foreground" />
    );
  }
  if (item.type === "knowledge") {
    return <BookOpenIcon className="size-4 shrink-0 text-primary" />;
  }
  if (item.type === "agent") {
    return <BotIcon className="size-4 shrink-0 text-primary" />;
  }
  if (item.type === "skill") {
    return <WandSparklesIcon className="size-4 shrink-0 text-primary" />;
  }
  return <PlugIcon className="size-4 shrink-0 text-muted-foreground" />;
}

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
  threadId,
  mention,
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
  const mentionPopupRef = useRef<HTMLDivElement>(null);
  const previousPositions = useRef(new Map<string, DOMRect>());
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const dictationBase = useRef("");
  const setDraftRef = useRef(setDraft);
  const [composing, setComposing] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [speechSupported, setSpeechSupported] = useState<boolean | null>(null);
  const [listening, setListening] = useState(false);
  const [modelSweep, setModelSweep] = useState(0);
  const [caretOffset, setCaretOffset] = useState<number | null>(null);
  const [dismissedMentionStart, setDismissedMentionStart] = useState<
    number | null
  >(null);
  const [mentionSelectedIndex, setMentionSelectedIndex] = useState(0);
  const [remoteKnowledge, setRemoteKnowledge] = useState<MentionItem[]>([]);
  const [remoteAgents, setRemoteAgents] = useState<MentionItem[]>([]);
  const [remoteFiles, setRemoteFiles] = useState<MentionItem[]>([]);
  const loadedCatalogRef = useRef(false);
  const loadedThreadFilesRef = useRef<string | null>(null);
  const previousQueryRef = useRef<string | null>(null);
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

  const resolvedCaret =
    caretOffset === null
      ? draft.length
      : Math.max(0, Math.min(caretOffset, draft.length));
  const activeMention =
    disabled || composing ? null : findActiveMentionQuery(draft, resolvedCaret);
  const mentionOpen =
    Boolean(activeMention) && dismissedMentionStart !== activeMention?.start;

  useEffect(() => {
    const nextQuery = activeMention?.query ?? null;
    if (previousQueryRef.current !== nextQuery) {
      previousQueryRef.current = nextQuery;
      setMentionSelectedIndex(0);
    }
  }, [activeMention?.query]);

  useEffect(() => {
    if (!mentionOpen || !activeMention) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (editor.current?.contains(target)) return;
      if (mentionPopupRef.current?.contains(target)) return;
      setDismissedMentionStart(activeMention.start);
    };

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [activeMention, mentionOpen]);

  useEffect(() => {
    if (!mentionOpen) return;
    let cancelled = false;

    if (!mention?.knowledgeBases && !mention?.agents && !loadedCatalogRef.current) {
      loadedCatalogRef.current = true;
      void Promise.resolve(listKnowledgeBases())
        .then((bases) => {
          if (cancelled || !Array.isArray(bases)) return;
          setRemoteKnowledge(
            bases.map((kb) => ({
              type: "knowledge",
              value: kb.name,
              label: kb.name,
              description: kb.description || "",
            })),
          );
        })
        .catch(() => {});

      void Promise.resolve(listAgents())
        .then((agents) => {
          if (cancelled || !Array.isArray(agents)) return;
          setRemoteAgents(
            agents
              .filter((agent) => agent.enabled)
              .map((agent) => ({
                type: "agent",
                value: agent.id,
                label: agent.name || agent.id,
                description: agent.description || "",
              })),
          );
        })
        .catch(() => {});
    }

    if (
      !mention?.files &&
      threadId &&
      loadedThreadFilesRef.current !== threadId
    ) {
      loadedThreadFilesRef.current = threadId;
      void Promise.resolve(listSandboxWorkspace(threadId, "/workspace"))
        .then((workspace) => {
          if (cancelled || !Array.isArray(workspace?.entries)) return;
          setRemoteFiles(
            workspace.entries.map((entry) => ({
              type: "file",
              value: entry.path,
              label: entry.name,
              description: entry.path,
              isDir: entry.kind === "directory",
            })),
          );
        })
        .catch(() => {});
    }

    return () => {
      cancelled = true;
    };
  }, [mention?.agents, mention?.files, mention?.knowledgeBases, mentionOpen, threadId]);

  useLayoutEffect(() => {
    const textarea = editor.current;
    if (!textarea) return;

    // Measure without a height transition so shrinking never reads the old height.
    textarea.style.height = "0px";
    const contentHeight = draft ? textarea.scrollHeight : COMPOSER_MIN_HEIGHT;
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

  const mentionQuery = activeMention?.query ?? "";
  const normalizedQuery = mentionQuery.trim().toLowerCase();

  const matchesQuery = (item: MentionItem) => {
    if (!normalizedQuery) return true;
    return [item.label, item.value, item.description]
      .filter(Boolean)
      .some((text) => String(text).toLowerCase().includes(normalizedQuery));
  };

  const mergedFileCandidates = (() => {
    const seen = new Set<string>();
    const list: MentionItem[] = [];
    const push = (item: MentionItem) => {
      if (!item.value || seen.has(item.value)) return;
      seen.add(item.value);
      list.push(item);
    };
    attachments.forEach((attachment) => {
      push({
        type: "file",
        value: attachment.file_name,
        label: attachment.file_name,
        description: attachment.content_type,
      });
    });
    (mention?.files ?? (threadId ? remoteFiles : [])).forEach(push);
    return list.filter(matchesQuery);
  })();

  const filteredKnowledgeBases = (
    mention?.knowledgeBases ?? remoteKnowledge
  ).filter(matchesQuery);

  const filteredAgents = (mention?.agents ?? remoteAgents).filter(matchesQuery);

  const flatMentionItems: MentionItem[] = [
    ...mergedFileCandidates,
    ...filteredKnowledgeBases,
    ...filteredAgents,
  ];

  const selectMentionItem = (item: MentionItem) => {
    if (disabled || !activeMention) return;
    const tokenText = `${formatMentionToken(item.type, item.value)} `;
    const nextDraft = replaceRawRange(
      draft,
      activeMention.start,
      activeMention.end,
      tokenText,
    );
    const nextCaret = activeMention.start + tokenText.length;
    setDismissedMentionStart(activeMention.start);
    setCaretOffset(nextCaret);
    setDraft(nextDraft);
    requestAnimationFrame(() => {
      const textarea = editor.current;
      if (!textarea) return;
      textarea.focus();
      textarea.setSelectionRange(nextCaret, nextCaret);
    });
  };

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
    setDismissedMentionStart(null);
    setCaretOffset(null);
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

  const onDraftChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    const nextValue = event.target.value;
    const caret = event.target.selectionStart ?? nextValue.length;
    setDismissedMentionStart(null);
    setCaretOffset(caret);
    setDraft(nextValue);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (mentionOpen && activeMention) {
      if (event.key === "Escape") {
        event.preventDefault();
        setDismissedMentionStart(activeMention.start);
        return;
      }
      if (flatMentionItems.length > 0) {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          setMentionSelectedIndex(
            (current) => (current + 1) % flatMentionItems.length,
          );
          return;
        }
        if (event.key === "ArrowUp") {
          event.preventDefault();
          setMentionSelectedIndex(
            (current) =>
              (current - 1 + flatMentionItems.length) %
              flatMentionItems.length,
          );
          return;
        }
        if (
          (event.key === "Enter" || event.key === "Tab") &&
          !event.shiftKey &&
          !event.nativeEvent.isComposing &&
          !composing
        ) {
          event.preventDefault();
          const chosen =
            flatMentionItems[mentionSelectedIndex] ?? flatMentionItems[0];
          if (chosen) selectMentionItem(chosen);
          return;
        }
      }
    }

    if (
      (event.key === "Backspace" || event.key === "Delete") &&
      !event.nativeEvent.isComposing &&
      !composing
    ) {
      const textarea = event.currentTarget;
      const start = textarea.selectionStart ?? draft.length;
      const end = textarea.selectionEnd ?? start;
      const direction =
        event.key === "Backspace" && start === end ? "backward" : "forward";
      const expandedRange = expandMentionDeletionRange(
        draft,
        start,
        end,
        direction,
      );
      if (expandedRange) {
        event.preventDefault();
        const nextDraft = replaceRawRange(
          draft,
          expandedRange.start,
          expandedRange.end,
          "",
        );
        setDismissedMentionStart(null);
        setCaretOffset(expandedRange.start);
        setDraft(nextDraft);
        requestAnimationFrame(() => {
          textarea.focus();
          textarea.setSelectionRange(expandedRange.start, expandedRange.start);
        });
        return;
      }
    }

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

  const getFlatIndex = (group: "file" | "knowledge" | "agent", index: number) => {
    if (group === "file") return index;
    if (group === "knowledge") return mergedFileCandidates.length + index;
    return mergedFileCandidates.length + filteredKnowledgeBases.length + index;
  };

  return (
    <form
      ref={composer}
      aria-label={t("Agent message composer")}
      aria-busy={uploading > 0}
      data-expanded={expanded}
      className="relative isolate flex w-full flex-col rounded-[1.4rem] border border-border bg-card px-3 pt-[0.8rem] pb-[0.6rem] shadow-[0_2px_8px_rgb(0_0_0/0.05)]"
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

      {mentionOpen && activeMention && !disabled && (
        <div
          ref={mentionPopupRef}
          role="listbox"
          aria-label={t("Mention suggestions")}
          onMouseDown={(event) => event.preventDefault()}
          className={` absolute inset-x-0 z-50 max-h-[280px] overflow-y-auto rounded-xl border border-border bg-popover py-2 text-popover-foreground shadow-lg ${
            placement === "top" ? "bottom-full mb-2" : "top-full mt-2"
          }`}
        >
          {mergedFileCandidates.length > 0 && (
            <div className="mb-1 last:mb-0">
              <div className="mb-0.5 border-b border-border/60 px-2.5 py-1 text-xs text-muted-foreground">
                {t("Files")}
              </div>
              {mergedFileCandidates.map((item, index) => {
                const flatIdx = getFlatIndex("file", index);
                const selected = flatIdx === mentionSelectedIndex;
                return (
                  <Button
                    key={`file-${item.value}`}
                    type="button"
                    variant="ghost"
                    role="option"
                    aria-selected={selected}
                    onMouseEnter={() => setMentionSelectedIndex(flatIdx)}
                    onClick={() => selectMentionItem(item)}
                    className={`mx-1 flex h-auto w-[calc(100%-0.5rem)] items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left text-[13px] font-normal ${
                      selected
                        ? "bg-selection text-selection-foreground hover:bg-selection hover:text-selection-foreground"
                        : "text-foreground"
                    }`}
                  >
                    <span className="flex min-w-0 items-center gap-2 font-medium">
                      <MentionItemIcon item={item} />
                      <span className="truncate">
                        <HighlightedText text={item.label} query={mentionQuery} />
                      </span>
                    </span>
                    {item.description && (
                      <span className="shrink-0 truncate text-xs text-muted-foreground">
                        <HighlightedText
                          text={item.description}
                          query={mentionQuery}
                        />
                      </span>
                    )}
                  </Button>
                );
              })}
            </div>
          )}

          {filteredKnowledgeBases.length > 0 && (
            <div className="mb-1 last:mb-0">
              <div className="mb-0.5 border-b border-border/60 px-2.5 py-1 text-xs text-muted-foreground">
                {t("Knowledge")}
              </div>
              {filteredKnowledgeBases.map((item, index) => {
                const flatIdx = getFlatIndex("knowledge", index);
                const selected = flatIdx === mentionSelectedIndex;
                return (
                  <Button
                    key={`kb-${item.value}`}
                    type="button"
                    variant="ghost"
                    role="option"
                    aria-selected={selected}
                    onMouseEnter={() => setMentionSelectedIndex(flatIdx)}
                    onClick={() => selectMentionItem(item)}
                    className={`mx-1 flex h-auto w-[calc(100%-0.5rem)] items-center justify-start gap-2 rounded-lg px-2.5 py-1.5 text-left text-[13px] font-normal ${
                      selected
                        ? "bg-selection text-selection-foreground hover:bg-selection hover:text-selection-foreground"
                        : "text-foreground"
                    }`}
                  >
                    <MentionItemIcon item={item} />
                    <span className="shrink-0 font-medium">
                      <HighlightedText text={item.label} query={mentionQuery} />
                    </span>
                    {item.description && (
                      <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                        <HighlightedText
                          text={item.description}
                          query={mentionQuery}
                        />
                      </span>
                    )}
                  </Button>
                );
              })}
            </div>
          )}

          {filteredAgents.length > 0 && (
            <div className="mb-1 last:mb-0">
              <div className="mb-0.5 border-b border-border/60 px-2.5 py-1 text-xs text-muted-foreground">
                {t("Agents")}
              </div>
              {filteredAgents.map((item, index) => {
                const flatIdx = getFlatIndex("agent", index);
                const selected = flatIdx === mentionSelectedIndex;
                return (
                  <Button
                    key={`agent-${item.value}`}
                    type="button"
                    variant="ghost"
                    role="option"
                    aria-selected={selected}
                    onMouseEnter={() => setMentionSelectedIndex(flatIdx)}
                    onClick={() => selectMentionItem(item)}
                    className={`mx-1 flex h-auto w-[calc(100%-0.5rem)] items-center justify-start gap-2 rounded-lg px-2.5 py-1.5 text-left text-[13px] font-normal ${
                      selected
                        ? "bg-selection text-selection-foreground hover:bg-selection hover:text-selection-foreground"
                        : "text-foreground"
                    }`}
                  >
                    <MentionItemIcon item={item} />
                    <span className="shrink-0 font-medium">
                      <HighlightedText text={item.label} query={mentionQuery} />
                    </span>
                    {item.description && (
                      <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                        <HighlightedText
                          text={item.description}
                          query={mentionQuery}
                        />
                      </span>
                    )}
                  </Button>
                );
              })}
            </div>
          )}

          {flatMentionItems.length === 0 && (
            <div className="px-3 py-3 text-center text-[13px] text-muted-foreground">
              {t("No matching items to mention")}
            </div>
          )}
        </div>
      )}

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
              className="flex h-9 items-center gap-2 rounded-md bg-muted px-3 text-xs text-muted-foreground motion-safe:animate-in motion-safe:fade-in motion-safe:zoom-in-95 motion-safe:duration-200"
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
        className="relative z-10 grid w-full grid-cols-[30px_minmax(0,1fr)_auto_30px_32px] items-center gap-x-1 gap-y-2"
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
            render={<Button variant="ghost" size="icon" />}
            type="button"
            disabled={disabled}
            aria-label={t("Action menu")}
            data-composer-control="actions"
            className="col-start-1 row-start-2 size-[30px] rounded-lg text-muted-foreground hover:text-foreground"
          >
            <PlusIcon className="transition-transform duration-200 group-aria-expanded/button:rotate-45 motion-reduce:transition-none" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            anchor={composer}
            side={placement}
            align="start"
            aria-label={t("Actions menu")}
            className="p-2"
          >
            <DropdownMenuItem
              className="gap-2 rounded-md px-2 py-1.5"
              onClick={() => fileInput.current?.click()}
            >
              <PaperclipIcon aria-hidden="true" />
              <span className="flex min-w-0 flex-col gap-0.5">
                <span>{t("Add attachment")}</span>
                <span className="text-xs text-muted-foreground">
                  {t("Upload files from your device")}
                </span>
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem disabled className="gap-2 rounded-md px-2 py-1.5">
              <PlugIcon aria-hidden="true" />
              <span className="flex min-w-0 flex-col gap-0.5">
                <span>{t("Connectors")}</span>
                <span className="text-xs text-muted-foreground">
                  {t("Not yet available")}
                </span>
              </span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Textarea
          ref={editor}
          value={draft}
          onChange={onDraftChange}
          onClick={(event) => {
            const caret =
              event.currentTarget.selectionStart ??
              event.currentTarget.value.length;
            setDismissedMentionStart(null);
            setCaretOffset(caret);
          }}
          onKeyDown={onKeyDown}
          onCompositionStart={() => setComposing(true)}
          onCompositionEnd={(event) => {
            setComposing(false);
            const caret =
              event.currentTarget.selectionStart ??
              event.currentTarget.value.length;
            setDismissedMentionStart(null);
            setCaretOffset(caret);
          }}
          disabled={disabled}
          aria-label={t("Message")}
          placeholder={listening ? t("Listening…") : t("Ask anything")}
          rows={1}
          className="col-span-full col-start-1 row-start-1 field-sizing-fixed max-h-[200px] min-h-11 min-w-0 resize-none rounded-none border-0 bg-transparent p-0 text-[15px] leading-[1.5] shadow-none focus-visible:ring-0 disabled:bg-transparent disabled:opacity-60"
        />

        <div
          data-composer-control="model"
          className="col-start-3 row-start-2 min-w-0"
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
            render={<Button variant="ghost" size="icon" />}
            type="button"
            disabled={disabled || running || speechSupported !== true}
            aria-label={dictationLabel}
            aria-pressed={listening}
            data-composer-control="dictation"
            onClick={toggleDictation}
            className="col-start-4 row-start-2 size-[30px] rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
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
                size="icon"
              />
            }
            type="button"
            disabled={actionDisabled}
            aria-label={running ? t("Cancel response") : t("Send message")}
            data-composer-control="submit"
            onClick={running ? cancel : submitMessage}
            className="col-start-5 row-start-2 rounded-full shadow-[0_2px_6px_rgb(0_0_0/0.08)] disabled:shadow-none"
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
