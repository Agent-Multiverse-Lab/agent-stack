import { useLayoutEffect, useRef, useState } from "react";
import { ChevronDownIcon } from "lucide-react";

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
    : selected?.display_name || selected?.name || t("Select model");

  return (
    <DropdownMenu
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) setActiveId(null);
      }}
    >
      <DropdownMenuTrigger
        render={<Button variant="ghost" size="lg" />}
        type="button"
        disabled={disabled || loading || available.length === 0}
        aria-label={t("Select model")}
        className="h-9 min-w-0 max-w-[10rem] gap-1 rounded-xl bg-muted/70 px-2.5 text-xs shadow-none transition-transform duration-150 hover:bg-muted active:scale-[0.96] motion-reduce:transform-none"
      >
        <span className="truncate">{triggerLabel}</span>
        <ChevronDownIcon
          className="size-3.5 transition-transform duration-200 group-aria-expanded/button:rotate-180 motion-reduce:transition-none"
          aria-hidden="true"
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        ref={content}
        side={placement}
        align="end"
        aria-label={t("Select model")}
        className="relative max-w-[min(20rem,calc(100vw-2rem))] min-w-64"
        onPointerLeave={() => setActiveId(null)}
      >
        {highlight && (
          <span
            aria-hidden="true"
            data-model-highlight=""
            className="pointer-events-none absolute inset-x-1 top-0 z-0 rounded-md bg-accent transition-[transform,height,opacity] duration-200 ease-out motion-reduce:transition-none"
            style={{
              height: highlight.height,
              transform: `translateY(${highlight.top}px)`,
            }}
          />
        )}
        {models.length === 0 ? (
          <DropdownMenuItem disabled>{t("No models available")}</DropdownMenuItem>
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
                disabled={!model.is_available}
                onPointerEnter={() => setActiveId(model.id)}
                onFocus={() => setActiveId(model.id)}
                className="relative z-10 min-h-10 gap-2 bg-transparent px-2 py-1.5 focus:bg-transparent"
              >
                <span className="min-w-0 flex-1 truncate">
                  {model.display_name || model.name}
                </span>
                <span className="max-w-24 truncate text-[0.6875rem] text-muted-foreground">
                  {model.version || model.provider}
                </span>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
