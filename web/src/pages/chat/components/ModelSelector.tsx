import { useLayoutEffect, useRef, useState } from "react";
import { ChevronDownIcon, CpuIcon } from "lucide-react";

import deepseekIcon from "@/assets/models/deepseek-color.svg";
import geminiIcon from "@/assets/models/gemini-color.svg";
import minimaxIcon from "@/assets/models/minimax-color.svg";
import ollamaIcon from "@/assets/models/ollama-color.svg";
import openaiIcon from "@/assets/models/openai.svg";
import qwenIcon from "@/assets/models/qwen-color.svg";
import vllmIcon from "@/assets/models/vllm-color.svg";
import zhipuIcon from "@/assets/models/zhipu-color.svg";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTranslation } from "@/i18n";
import type { ChatModelOption } from "@/types/model";

type HighlightBox = {
  height: number;
  top: number;
};

const modelIcons: Record<string, string> = {
  deepseek: deepseekIcon,
  gemini: geminiIcon,
  minimax: minimaxIcon,
  ollama: ollamaIcon,
  openai: openaiIcon,
  qwen: qwenIcon,
  vllm: vllmIcon,
  zhipu: zhipuIcon,
};

export default function ModelSelector({
  models,
  selectedId,
  loading,
  disabled,
  placement,
  select,
}: {
  models: ChatModelOption[];
  selectedId: string;
  loading: boolean;
  disabled: boolean;
  placement: "top" | "bottom";
  select: (id: string) => void;
}) {
  const { t } = useTranslation();
  const selected = models.find((model) => model.id === selectedId);
  const available = models.filter((model) => model.is_available);
  const content = useRef<HTMLDivElement>(null);
  const items = useRef(new Map<string, HTMLDivElement>());
  const [open, setOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<HighlightBox | null>(null);

  useLayoutEffect(() => {
    const popup = content.current;
    const item = activeId ? items.current.get(activeId) : undefined;
    if (!open || !popup || !item) {
      setHighlight(null);
      return;
    }

    const popupRect = popup.getBoundingClientRect();
    const itemRect = item.getBoundingClientRect();
    setHighlight({
      height: itemRect.height,
      top: itemRect.top - popupRect.top,
    });
  }, [activeId, open]);

  const triggerLabel = loading
    ? t("Loading")
    : selected?.name || t("Select model");

  return (
    <DropdownMenu
      modal={false}
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) setActiveId(null);
      }}
    >
      <DropdownMenuTrigger
        render={<Button type="button" variant="ghost" />}
        disabled={disabled || loading || available.length === 0}
        aria-label={t("Select model")}
        title={triggerLabel}
        className="flex h-[30px] w-auto min-w-0 max-w-[168px] shrink-0 items-center gap-1 rounded-lg px-2 text-[13px] leading-none font-normal text-muted-foreground hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground"
      >
        <span className="truncate">{triggerLabel}</span>
        <ChevronDownIcon
          className="size-3.5 shrink-0 opacity-70 transition-transform duration-200 group-aria-expanded/button:rotate-180 motion-reduce:transition-none"
          aria-hidden="true"
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        ref={content}
        side={placement}
        align="end"
        sideOffset={8}
        aria-label={t("Select model")}
        className="relative w-64 max-w-[calc(100vw-2rem)] rounded-lg p-1"
        onPointerLeave={() => setActiveId(null)}
      >
        {highlight && (
          <span
            aria-hidden="true"
            data-model-highlight=""
            className="pointer-events-none absolute inset-x-1.5 top-0 z-0 rounded-md bg-accent transition-[transform,height] duration-200 ease-out motion-reduce:transition-none"
            style={{
              height: highlight.height,
              transform: `translateY(${highlight.top}px)`,
            }}
          />
        )}
        {models.length === 0 ? (
          <DropdownMenuItem disabled className="rounded-md px-2 py-1.5">
            {t("No models available")}
          </DropdownMenuItem>
        ) : (
          <DropdownMenuRadioGroup
            value={selectedId}
            onValueChange={(value) => {
              if (value) select(value);
            }}
          >
            {models.map((model) => (
              <DropdownMenuRadioItem
                key={model.id}
                ref={(node) => {
                  if (node) items.current.set(model.id, node);
                  else items.current.delete(model.id);
                }}
                value={model.id}
                closeOnClick
                disabled={!model.is_available}
                onPointerEnter={() => setActiveId(model.id)}
                onFocus={() => setActiveId(model.id)}
                className="relative z-10 rounded-md bg-transparent py-1.5 pr-8 pl-2 focus:bg-transparent data-checked:bg-selection data-checked:text-selection-foreground data-checked:focus:bg-selection data-checked:focus:text-selection-foreground [&_[data-slot=dropdown-menu-radio-item-indicator]]:right-3"
              >
                <span className="flex min-w-0 flex-1 items-center gap-2" title={model.name}>
                  {modelIcons[model.icon] ? (
                    <img src={modelIcons[model.icon]} alt="" className="size-4 shrink-0" />
                  ) : (
                    <CpuIcon className="size-4 shrink-0" aria-hidden="true" />
                  )}
                  <span className="truncate font-medium">
                    {model.name}
                  </span>
                </span>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
