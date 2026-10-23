import { Layers } from "lucide-react";
import { useTranslation } from "@/i18n";

export default function Satellite() {
  const { t } = useTranslation();
  return (
    <main
      className="flex h-full min-h-0 w-full flex-col bg-background text-foreground"
      aria-label={t("Satellite")}
    >
      <header className="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-(--page-padding)">
        <h1 className="truncate text-sm font-medium">{t("Satellite")}</h1>
      </header>
      <div className="flex min-h-0 flex-1 items-center justify-center bg-card p-(--page-padding) pb-[6rem]">
        <section
          className="flex w-full max-w-[30rem] flex-col items-center text-center"
          aria-labelledby="satellite-heading"
        >
          <Layers
            className="mb-4 text-foreground"
            size={44}
            strokeWidth={1.35}
            aria-hidden
          />
          <h2
            id="satellite-heading"
            className="m-0 text-[clamp(1.6rem,4vw,2rem)] font-[550] leading-[1.25] tracking-[-0.035em]"
          >
            {t("Satellite unavailable")}
          </h2>
        </section>
      </div>
    </main>
  );
}
