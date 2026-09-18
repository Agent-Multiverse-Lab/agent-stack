import { File as FileIcon, X } from "lucide-react";
import { Tooltip } from "antd";
import type { ChatAttachment } from "@/types/attachment";

export function Attachment({
  attachment,
  remove,
}: {
  attachment: ChatAttachment;
  remove?: (id: string) => void;
}) {
  return (
    <li
      className={`grid h-11 max-w-[17rem] min-w-0 shrink-0 items-center gap-2 rounded-full border border-graphite/12 bg-paper p-1 text-graphite ${remove ? "grid-cols-[2rem_minmax(0,1fr)_2rem]" : "grid-cols-[2rem_minmax(0,1fr)] pr-3"}`}
    >
      <span
        className="grid size-8 place-items-center overflow-hidden rounded-full bg-graphite/6 text-slate"
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
        <Tooltip title={`Remove ${attachment.file_name}`}>
          <button
            type="button"
            className="grid size-7 place-items-center rounded-full text-graphite/58 hover:bg-graphite hover:text-paper"
            aria-label={`Remove attachment ${attachment.file_name}`}
            onClick={() => remove(attachment.file_id)}
          >
            <X size={14} />
          </button>
        </Tooltip>
      )}
    </li>
  );
}
