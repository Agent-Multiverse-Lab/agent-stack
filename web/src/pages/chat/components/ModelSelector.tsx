import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import deepseekLogo from "@/assets/models/deepseek-color.svg";
import qwenLogo from "@/assets/models/qwen-color.svg";
import minimaxLogo from "@/assets/models/minimax-color.svg";
import geminiLogo from "@/assets/models/gemini-color.svg";
import openaiLogo from "@/assets/models/openai.svg";
import zhipuLogo from "@/assets/models/zhipu-color.svg";
import type { ChatModelOption } from "@/types/model";

const families = [
  { id: "qwen", name: "千问", logo: qwenLogo },
  { id: "deepseek", name: "DeepSeek", logo: deepseekLogo },
  { id: "minimax", name: "MiniMax", logo: minimaxLogo },
  { id: "gemini", name: "Gemini", logo: geminiLogo },
  { id: "openai", name: "OpenAI", logo: openaiLogo },
  { id: "zhipu", name: "智谱", logo: zhipuLogo },
];
const belongsTo = (model: ChatModelOption, family: string) =>
  model.icon === family ||
  (family === "minimax" && model.name.toLowerCase().startsWith("minimax")) ||
  (family === "zhipu" && /^(glm|chatglm)/i.test(model.name));
const point = (angle: number, radius: number) => ({
  x: 100 + Math.cos((angle * Math.PI) / 180) * radius,
  y: 100 + Math.sin((angle * Math.PI) / 180) * radius,
});
const sectors = families.map((family, position) => {
  const start = point(position * 60 - 120, 98);
  const end = point(position * 60 - 60, 98);
  const icon = point(position * 60 - 90, 64);
  return {
    ...family,
    path: `M100 100 L${start.x} ${start.y} A98 98 0 0 1 ${end.x} ${end.y} Z`,
    x: icon.x - 13,
    y: icon.y - 13,
  };
});

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
  const [open, setOpen] = useState(false);
  const [familyIndex, setFamilyIndex] = useState<number | null>(null);
  const [listOpen, setListOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const dial = useRef<SVGSVGElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const selected = models.find((model) => model.id === selectedId);
  const selectedFamily =
    selected && families.find((family) => belongsTo(selected, family.id));
  const family = familyIndex === null ? null : families[familyIndex];
  const familyModels = family
    ? models.filter((model) => belongsTo(model, family.id))
    : [];
  const controlDisabled =
    disabled ||
    loading ||
    !models.some((model) => families.some((item) => item.id === model.icon));
  function close(restore = false) {
    setOpen(false);
    if (restore) requestAnimationFrame(() => trigger.current?.focus());
  }
  useEffect(() => {
    const outside = (event: Event) => {
      if (open && !container.current?.contains(event.target as Node)) close();
    };
    const escape = (event: globalThis.KeyboardEvent) => {
      if (open && event.key === "Escape") {
        event.preventDefault();
        close(true);
      }
    };
    const blur = () => {
      if (open) close();
    };
    window.addEventListener("pointerdown", outside);
    window.addEventListener("focusin", outside);
    window.addEventListener("keydown", escape);
    window.addEventListener("blur", blur);
    return () => {
      window.removeEventListener("pointerdown", outside);
      window.removeEventListener("focusin", outside);
      window.removeEventListener("keydown", escape);
      window.removeEventListener("blur", blur);
    };
  }, [open]);
  useEffect(() => {
    if (controlDisabled) setOpen(false);
  }, [controlDisabled]);
  function showModels(index: number) {
    setFamilyIndex(index);
    setListOpen(true);
    requestAnimationFrame(() => list.current?.focus());
  }
  function keydown(event: KeyboardEvent<SVGSVGElement>) {
    if (
      ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)
    ) {
      event.preventDefault();
      const direction =
        event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1;
      setFamilyIndex((previous) =>
        previous === null
          ? 0
          : (previous + direction + families.length) % families.length,
      );
    } else if (
      (event.key === "Enter" || event.key === " ") &&
      familyIndex !== null
    ) {
      event.preventDefault();
      showModels(familyIndex);
    }
  }
  return (
    <div ref={container} className="relative min-w-0 font-sans">
      <button
        ref={trigger}
        type="button"
        className="grid size-10 shrink-0 place-items-center rounded-full hover:bg-mist disabled:opacity-45"
        disabled={controlDisabled}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="选择模型"
        title={loading ? "模型加载中" : (selected?.name ?? "选择模型")}
        onClick={() => {
          if (open) close();
          else {
            setFamilyIndex(null);
            setListOpen(false);
            setOpen(true);
            requestAnimationFrame(() => dial.current?.focus());
          }
        }}
      >
        {selectedFamily ? (
          <img
            src={selectedFamily.logo}
            className="size-6"
            alt=""
            draggable={false}
          />
        ) : (
          <svg
            className="size-6 text-slate"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="9" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        )}
      </button>
      {open && (
        <div
          className={`absolute right-0 z-60 ${placement === "top" ? "bottom-full mb-3" : "top-full mt-3"}`}
          role="dialog"
          aria-label="选择模型家族和型号"
        >
          {listOpen && family ? (
            <div
              ref={list}
              tabIndex={-1}
              className="w-[min(16rem,calc(100vw-6rem))] rounded-2xl border border-graphite/10 bg-paper p-1.5 outline-none"
              aria-label={`${family.name}型号列表`}
            >
              <button
                type="button"
                className="rounded-lg px-3 py-2 text-xs text-slate hover:bg-mist"
                onClick={() => {
                  setListOpen(false);
                  requestAnimationFrame(() => dial.current?.focus());
                }}
              >
                返回
              </button>
              <div className="max-h-[min(18rem,45dvh)] overflow-y-auto">
                {familyModels.map((model) => (
                  <button
                    key={model.id}
                    type="button"
                    className="block w-full rounded-xl px-3 py-2.5 text-left text-sm hover:bg-mist disabled:opacity-40"
                    disabled={!model.is_available}
                    aria-pressed={model.id === selectedId}
                    onClick={() => {
                      select(model.id);
                      close(true);
                    }}
                  >
                    {model.name}
                  </button>
                ))}
                {!familyModels.length && (
                  <p className="px-3 py-4 text-xs text-slate">
                    暂无已配置的型号
                  </p>
                )}
              </div>
            </div>
          ) : (
            <svg
              ref={dial}
              className="block w-[min(12rem,calc(100vw-6rem))] rounded-full bg-paper outline-none"
              viewBox="0 0 200 200"
              tabIndex={0}
              role="group"
              aria-label="选择模型家族，方向键切换，Enter 展开型号"
              onKeyDown={keydown}
            >
              {sectors.map((item, position) => (
                <path
                  key={item.id}
                  d={item.path}
                  fill={familyIndex === position ? "#e8e8ef" : "#f7f7f7"}
                  stroke="white"
                  strokeWidth="2"
                  role="button"
                  tabIndex={0}
                  aria-label={item.name}
                  aria-pressed={familyIndex === position}
                  className="cursor-pointer"
                  onPointerEnter={() => setFamilyIndex(position)}
                  onFocus={() => setFamilyIndex(position)}
                  onClick={() => showModels(position)}
                />
              ))}
              {sectors.map((item) => (
                <image
                  key={item.id}
                  href={item.logo}
                  x={item.x}
                  y={item.y}
                  width="26"
                  height="26"
                  className="pointer-events-none"
                  aria-hidden="true"
                />
              ))}
            </svg>
          )}
        </div>
      )}
    </div>
  );
}
