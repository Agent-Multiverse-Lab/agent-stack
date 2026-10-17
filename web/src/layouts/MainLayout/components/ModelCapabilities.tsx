import {
  AudioLines,
  Brain,
  CircleHelp,
  Code2,
  MessageSquare,
  ScanEye,
  Video,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useTranslation } from "@/i18n";
import type { ChatCapability } from "@/types/model";

const capabilityDetails: Record<ChatCapability, { icon: LucideIcon; label: string }> = {
  chat: { icon: MessageSquare, label: "Chat" },
  vision: { icon: ScanEye, label: "Vision" },
  reasoning: { icon: Brain, label: "Reasoning" },
  tools: { icon: Wrench, label: "Tools" },
  code: { icon: Code2, label: "Code" },
  audio: { icon: AudioLines, label: "Audio" },
  video: { icon: Video, label: "Video" },
};

export function ModelCapabilities({ capabilities }: { capabilities: ChatCapability[] }) {
  const { t } = useTranslation();

  if (!capabilities.length) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-normal text-muted-foreground">
        <CircleHelp aria-hidden="true" className="size-3.5 shrink-0" />
        {t("Capabilities not provided")}
      </span>
    );
  }

  return (
    <ul aria-label={t("Model capabilities")} className="flex flex-wrap items-center gap-1.5">
      {capabilities.map((capability) => {
        const { icon: Icon, label } = capabilityDetails[capability];
        return (
          <li key={capability} className="flex">
            <Badge variant="secondary" className="gap-1.5 font-normal">
              <Icon aria-hidden="true" />
              {t(label)}
            </Badge>
          </li>
        );
      })}
    </ul>
  );
}
