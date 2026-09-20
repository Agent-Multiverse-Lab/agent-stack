import { File as FileIcon, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { ChatAttachment } from "@/types/attachment";
import { useTranslation } from "@/i18n";

export function Attachment({
  attachment,
  remove,
}: {
  attachment: ChatAttachment;
  remove?: (id: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <li
      className={`grid h-11 max-w-[17rem] min-w-0 shrink-0 items-center gap-2 rounded-full border border-border bg-background p-1 text-foreground motion-safe:animate-in motion-safe:fade-in motion-safe:zoom-in-95 motion-safe:duration-200 ${remove ? "grid-cols-[2rem_minmax(0,1fr)_2rem]" : "grid-cols-[2rem_minmax(0,1fr)] pr-3"}`}
    >
      <span
        className="grid size-8 place-items-center overflow-hidden rounded-full bg-muted text-muted-foreground"
        aria-hidden="true"
      >
        {attachment.content_type.startsWith("image/") &&
        attachment.access_url ? (
          <img
            src={attachment.access_url}
            alt=""
            className="size-full object-cover"
          />
        ) : (
          <FileIcon size={15} />
        )}
      </span>
      <strong
        className="min-w-0 truncate text-sm font-medium"
        title={attachment.file_name}
      >
        {attachment.file_name}
      </strong>
      {remove && (
        <Tooltip>
          <TooltipTrigger
            render={<Button variant="ghost" size="icon-sm" />}
            type="button"
            className="rounded-full text-muted-foreground transition-transform duration-150 hover:bg-muted hover:text-foreground active:scale-90 motion-reduce:transform-none"
            aria-label={t("Remove attachment {{name}}", { name: attachment.file_name })}
            onClick={() => remove(attachment.file_id)}
          >
            <X size={14} />
          </TooltipTrigger>
          <TooltipContent>{t("Remove attachment {{name}}", { name: attachment.file_name })}</TooltipContent>
        </Tooltip>
      )}
    </li>
  );
}
