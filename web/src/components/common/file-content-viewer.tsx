import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertCircle, FileText, LoaderCircle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTranslation } from "@/i18n";

interface FileContentViewerProps {
  path: string;
  content: string;
  loading?: boolean;
  error?: string;
  truncated?: boolean;
}

function isMarkdownPath(path: string) {
  return /\.(md|markdown)$/i.test(path);
}

export function FileContentViewer({
  path,
  content,
  loading = false,
  error = "",
  truncated = false,
}: FileContentViewerProps) {
  const { t } = useTranslation();
  const canPreviewMarkdown = isMarkdownPath(path);

  if (loading) {
    return (
      <div className="grid min-h-56 place-items-center text-sm text-muted-foreground">
        <div className="flex items-center gap-2">
          <LoaderCircle className="size-4 animate-spin" />
          {t("Loading file content…")}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>{t("Unable to preview file")}</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  const source = (
    <pre className="min-h-56 overflow-auto bg-muted/25 p-4 font-mono text-xs leading-5 whitespace-pre text-foreground">
      <code>{content}</code>
    </pre>
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {truncated ? (
        <div className="border-b border-amber-500/25 bg-amber-500/10 px-4 py-2 text-xs text-amber-800 dark:text-amber-300">
          {t("This preview is truncated.")}
        </div>
      ) : null}

      {canPreviewMarkdown ? (
        <Tabs defaultValue="preview" className="min-h-0 flex-1">
          <TabsList className="h-10 w-full justify-start gap-5 border-b px-4">
            <TabsTrigger value="preview" className="h-10 border-b-2 border-transparent px-0 data-active:border-foreground">
              {t("Rendered")}
            </TabsTrigger>
            <TabsTrigger value="source" className="h-10 border-b-2 border-transparent px-0 data-active:border-foreground">
              {t("Source")}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="preview" className="min-h-0 overflow-auto p-5">
            {content ? (
              <article className="chat-markdown max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
              </article>
            ) : (
              <EmptyFile />
            )}
          </TabsContent>
          <TabsContent value="source" className="min-h-0 overflow-auto">
            {content ? source : <EmptyFile />}
          </TabsContent>
        </Tabs>
      ) : content ? (
        source
      ) : (
        <EmptyFile />
      )}
    </div>
  );
}

function EmptyFile() {
  const { t } = useTranslation();
  return (
    <div className="grid min-h-56 place-items-center text-sm text-muted-foreground">
      <div className="flex flex-col items-center gap-2">
        <FileText className="size-6 opacity-60" />
        {t("This file is empty")}
      </div>
    </div>
  );
}
