import { useState } from "react";
import { AlertCircle, ImageOff, LoaderCircle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useTranslation } from "@/i18n";

export interface WorkspaceImagePreviewProps {
  name: string;
  imageUrl: string;
  loading?: boolean;
  error?: string;
}

export function WorkspaceImagePreview({
  name,
  imageUrl,
  loading = false,
  error = "",
}: WorkspaceImagePreviewProps) {
  const { t } = useTranslation();
  const [loadFailed, setLoadFailed] = useState(false);

  if (loading) {
    return (
      <div className="grid min-h-56 flex-1 place-items-center text-sm text-muted-foreground">
        <div className="flex items-center gap-2">
          <LoaderCircle className="size-4 animate-spin" />
          {t("Loading file content…")}
        </div>
      </div>
    );
  }

  if (error || loadFailed) {
    return (
      <div className="p-4">
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>{t("Unable to preview file")}</AlertTitle>
          <AlertDescription>{error || t("Unable to preview file")}</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!imageUrl) {
    return (
      <div className="grid min-h-56 flex-1 place-items-center text-sm text-muted-foreground">
        <div className="flex flex-col items-center gap-2">
          <ImageOff className="size-6 opacity-60" />
          {t("This file is empty")}
        </div>
      </div>
    );
  }

  return (
    <div className="grid min-h-56 flex-1 place-items-center overflow-auto p-6">
      <img
        src={imageUrl}
        alt={name}
        onError={() => setLoadFailed(true)}
        className="max-h-full max-w-full rounded-md object-contain"
      />
    </div>
  );
}

export default WorkspaceImagePreview;
