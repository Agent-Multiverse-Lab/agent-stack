import { Layers } from "lucide-react";
import { useTranslation } from "@/i18n";

export default function StaticPage() {
  const { t } = useTranslation();
  return (
    <main
      className="flex h-full min-h-0 w-full items-center justify-center bg-background px-5 pb-[6rem] text-foreground"
      aria-label={t("Static")}
    >
      <section
        className="flex w-full max-w-[30rem] flex-col items-center text-center"
        aria-labelledby="static-heading"
      >
        <Layers
          className="mb-4 text-foreground"
          size={44}
          strokeWidth={1.35}
          aria-hidden
        />
        <p className="m-0 mb-3 inline-flex items-center gap-2 font-mono text-[0.66rem] uppercase tracking-[0.04em] text-muted-foreground">
          <span
            className="h-[5px] w-[5px] rounded-full bg-muted-foreground"
            aria-hidden
          />
          <span>{t("Backend not connected")}</span>
        </p>
        <h2
          id="static-heading"
          className="m-0 text-[clamp(1.6rem,4vw,2rem)] font-[550] leading-[1.25] tracking-[-0.035em]"
        >
          {t("Static is not connected")}
        </h2>
        <p className="m-0 mt-3 max-w-[27rem] text-sm leading-[1.625] text-muted-foreground">
          {t("Static content will be available here after the backend is connected.")}
        </p>
      </section>
    </main>
  );
}
