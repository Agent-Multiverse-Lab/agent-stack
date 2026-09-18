import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ChatModelOption } from "@/types/model";
import { useTranslation } from "@/i18n";

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

  return (
    <Select
      value={selectedId || null}
      disabled={disabled || loading || !models.some((model) => model.is_available)}
      onValueChange={(value) => {
        if (value) select(value);
      }}
    >
      <SelectTrigger
        aria-label={t("Select model")}
        title={loading ? t("Loading models") : (selected?.display_name || selected?.name || t("Select model"))}
        className="h-10 min-w-0 max-w-[9rem] rounded-full border-graphite/10 bg-mist/80 px-3 text-xs"
      >
        <SelectValue placeholder={loading ? t("Loading") : t("Select model")} />
      </SelectTrigger>
      <SelectContent
        side={placement}
        align="end"
        alignItemWithTrigger={false}
        className="max-w-[min(20rem,calc(100vw-2rem))] min-w-56"
      >
        {models.map((model) => (
          <SelectItem key={model.id} value={model.id} disabled={!model.is_available}>
            {model.display_name || model.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
