import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslation } from "@/i18n";

const chevron = Array.from({ length: 9 }, (_, i) => {
  const r = Math.floor(i / 3),
    c = i % 3;
  return (c + Math.abs(r - 1)) * 90;
});

const ORBIT_ORDER = [0, 1, 2, 5, 8, 7, 6, 3];
const orbit = Array.from({ length: 9 }, (_, i) => {
  const k = ORBIT_ORDER.indexOf(i);
  return k === -1 ? null : k * 110;
});

const PATTERNS: Record<
  string,
  { delays: (number | null)[]; dur: number; round: boolean }
> = {
  Drive: { delays: chevron, dur: 650, round: false },
  Dots: { delays: chevron, dur: 650, round: true },
  Orbit: { delays: orbit, dur: 950, round: false },
};

function LoaderGrid({
  delays,
  dur,
  round,
}: {
  delays: (number | null)[];
  dur: number;
  round: boolean;
}) {
  return (
    <span
      aria-hidden="true"
      className="grid shrink-0 grid-cols-[repeat(3,4px)] gap-[1.5px]"
    >
      {delays.map((delay, index) => (
        <span
          key={index}
          className={`thinking-pixel size-[4px] bg-foreground ${round ? "rounded-full" : "rounded-[1px]"}`}
          style={{
            opacity: delay === null ? 0.07 : 0.15,
            animation:
              delay === null
                ? "none"
                : `pixel-on ${dur}ms ease-in-out ${delay}ms infinite`,
          }}
        />
      ))}
    </span>
  );
}

function ElapsedTime({ startedAt }: { startedAt: number }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.max(0, now - startedAt) / 1000;
  return (
    <span
      className="font-mono text-[12px] text-muted-foreground tabular-nums"
      aria-hidden="true"
    >
      {seconds < 60
        ? `${seconds.toFixed(1)}s`
        : `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(1)}s`}
    </span>
  );
}

export function Thinking({
  label,
  variant = "Drive",
  videoSrc = "https://95dnc2a95qgwt9ff.public.blob.vercel-storage.com/subway-surfers-min.mp4",
  children,
  startedAt,
}: {
  label?: string;
  variant?: string;
  videoSrc?: string;
  children?: ReactNode;
  startedAt?: number | null;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(true);
  const [videoOk, setVideoOk] = useState(true);
  const surfer = variant === "Surfer";
  const resolvedLabel = label ?? (surfer ? "Subway surfing" : "Thinking");
  const { delays, dur, round } = PATTERNS[variant] ?? PATTERNS.Drive;

  const labelEl = (
    <span
      className="thinking-shimmer bg-clip-text text-[13px] font-medium text-transparent"
      style={{
        backgroundImage:
          "linear-gradient(90deg, var(--muted-foreground) 35%, var(--foreground) 50%, var(--muted-foreground) 65%)",
        backgroundSize: "200% 100%",
        animation: "shimmer-text 1.4s linear infinite",
      }}
    >
      {t(resolvedLabel)}
    </span>
  );
  const elapsedEl =
    typeof startedAt === "number" && Number.isFinite(startedAt) ? (
      <ElapsedTime key={startedAt} startedAt={startedAt} />
    ) : null;

  if (surfer) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex w-fit flex-col items-start py-1"
      >
        <div className="flex items-center gap-2.5">
          <LoaderGrid {...PATTERNS.Drive} />
          {labelEl}
          {elapsedEl}
        </div>

        <div
          className="mt-2 w-56 overflow-hidden rounded-[10px] shadow-md"
          style={{
            animation: "pop-in 200ms cubic-bezier(0.16,1,0.3,1) both",
            transformOrigin: "top left",
          }}
        >
          <div className="relative aspect-video w-full bg-popover">
            {videoOk ? (
              <video
                src={videoSrc}
                autoPlay
                muted
                loop
                playsInline
                onError={() => setVideoOk(false)}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full flex-col items-center justify-center gap-1.5">
                <LoaderGrid {...PATTERNS.Drive} />
                <span className="px-3 text-center font-mono text-[10px] text-muted-foreground">
                  {t("Video unavailable")}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <Collapsible
      open={expanded}
      onOpenChange={setExpanded}
      className="w-full max-w-[38rem]"
    >
      <div
        className="flex w-fit items-center gap-2.5 py-1"
        role="status"
        aria-live="polite"
      >
        <LoaderGrid delays={delays} dur={dur} round={round} />
        {labelEl}
        {elapsedEl}
        {children && (
          <CollapsibleTrigger
            render={<Button variant="ghost" size="icon-sm" />}
            aria-label={
              expanded
                ? t("Collapse thinking details")
                : t("Expand thinking details")
            }
          >
            <ChevronDown size={16} />
          </CollapsibleTrigger>
        )}
      </div>
      {children && (
        <CollapsibleContent className="relative mt-1 ml-[5px] min-w-0 border-l border-border py-1 pl-5">
          {children}
        </CollapsibleContent>
      )}
    </Collapsible>
  );
}

export default Thinking;
