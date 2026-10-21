import { File as FileIcon, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { ChatAttachment } from "@/pages/chat/types";
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
      className={`relative grid w-[220px] min-w-0 shrink-0 grid-cols-[40px_minmax(0,1fr)] items-center gap-3 rounded-xl border border-border bg-background py-2.5 pl-3 text-foreground ${remove ? "pr-[34px]" : "pr-3"}`}
    >
      <span
        className="grid size-10 place-items-center overflow-hidden rounded-[10px] bg-muted text-muted-foreground"
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
        className="min-w-0 truncate text-sm leading-[1.35] font-semibold"
        title={attachment.file_name}
      >
        {attachment.file_name}
      </strong>
      {remove && (
        <Tooltip>
          <TooltipTrigger
            render={<Button variant="ghost" size="icon-sm" />}
            type="button"
            className="absolute top-1.5 right-1.5 size-5 rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
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
