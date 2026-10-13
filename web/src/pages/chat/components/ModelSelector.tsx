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
        render={<Button type="button" variant="ghost" />}
        disabled={disabled || loading || available.length === 0}
        aria-label={t("Select model")}
        className="flex h-10 min-w-0 max-w-48 shrink-0 items-center gap-1.5 rounded-full px-3 text-sm font-medium text-muted-foreground transition-[color,background-color,transform] duration-150 hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground active:scale-[0.96] motion-reduce:transform-none"
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
        className="relative w-64 max-w-[calc(100vw-2rem)] rounded-2xl p-1.5"
        onPointerLeave={() => setActiveId(null)}
      >
        {highlight && (
          <span
            aria-hidden="true"
            data-model-highlight=""
            className="pointer-events-none absolute inset-x-1.5 top-0 z-0 rounded-xl bg-accent transition-[transform,height] duration-200 ease-out motion-reduce:transition-none"
            style={{
              height: highlight.height,
              transform: `translateY(${highlight.top}px)`,
            }}
          />
        )}
        {models.length === 0 ? (
          <DropdownMenuItem disabled className="rounded-xl px-3 py-2.5">
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
                disabled={!model.is_available}
                onPointerEnter={() => setActiveId(model.id)}
                onFocus={() => setActiveId(model.id)}
                className="relative z-10 rounded-xl bg-transparent py-2 pr-9 pl-3 focus:bg-transparent data-checked:bg-selection data-checked:text-selection-foreground data-checked:focus:bg-selection data-checked:focus:text-selection-foreground [&_[data-slot=dropdown-menu-radio-item-indicator]]:right-3"
              >
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="truncate font-medium">
                    {model.display_name || model.name}
                  </span>
                  {(model.provider || model.version) && (
                    <span className="truncate text-xs text-muted-foreground">
                      {[model.provider, model.version].filter(Boolean).join(" · ")}
                    </span>
                  )}
                </span>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
