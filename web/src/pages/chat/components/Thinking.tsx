import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ChevronDown, LoaderCircle } from "lucide-react";

export function Thinking({
  label = "Thinking",
  children,
}: {
  label?: string;
  children?: ReactNode;
}) {
  const [elapsed, setElapsed] = useState(0);
  const [expanded, setExpanded] = useState(true);
  useEffect(() => {
    const started = performance.now();
    const timer = window.setInterval(
      () => setElapsed(performance.now() - started),
      100,
    );
    return () => clearInterval(timer);
  }, []);
  const seconds = elapsed / 1000;
  return (
    <section className="w-full max-w-[38rem]">
      <div
        className="flex w-fit items-center gap-2.5 py-1"
        role="status"
        aria-live="polite"
      >
        <LoaderCircle size={16} className="animate-spin text-slate" />
        <span className="text-[13px] font-medium">{label}</span>
        <span
          className="font-utility text-xs tabular-nums text-slate"
          aria-hidden="true"
        >
          {seconds < 60
            ? `${seconds.toFixed(1)}s`
            : `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(1)}s`}
        </span>
        {children && (
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={
              expanded ? "Collapse thinking details" : "Expand thinking details"
            }
            onClick={() => setExpanded(!expanded)}
          >
            <ChevronDown size={16} />
          </button>
        )}
      </div>
      {children && expanded && (
        <div className="relative mt-1 ml-[5px] min-w-0 border-l border-graphite/12 py-1 pl-5">
          {children}
        </div>
      )}
    </section>
  );
}
