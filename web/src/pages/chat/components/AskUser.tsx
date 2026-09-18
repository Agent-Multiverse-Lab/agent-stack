import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { InteractionRequired } from "@/types/chat";

export function AskUser({
  interaction,
  disabled,
  submit,
}: {
  interaction: InteractionRequired;
  disabled: boolean;
  submit: (answers: Record<string, string>) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [index, setIndex] = useState(0);
  const question = interaction.questions[index];
  const allAnswered =
    interaction.questions.length > 0 &&
    interaction.questions.every((item) =>
      item.options.some((option) => option.value === answers[item.question_id]),
    );
  return (
    <article
      className="w-full max-w-[36rem] overflow-hidden rounded-[1.25rem] border border-graphite/10 bg-paper shadow-[0_18px_48px_rgba(13,13,13,0.08)]"
      aria-label="Agent questions"
    >
      <header className="flex items-center gap-3 border-b border-graphite/8 px-5 py-4">
        <span className="grid size-9 place-items-center rounded-full bg-graphite text-paper">
          ?
        </span>
        <div>
          <p className="font-utility text-[0.66rem] font-bold uppercase tracking-[0.12em] text-slate">
            Input required
          </p>
          <p className="text-sm font-semibold">Agent needs your choice</p>
        </div>
      </header>
      <div className="relative h-[min(22rem,45dvh)] overflow-y-auto">
        <fieldset
          className="m-0 min-w-0 border-0 px-5 py-5"
          disabled={disabled}
        >
          {question && (
            <>
              <h3 className="break-words text-[0.95rem] font-medium leading-6">
                {question.question}
              </h3>
              <p className="mt-2 text-xs text-slate">
                选择后自动进入下一题，可用下方箭头返回修改。
              </p>
              <div className="mt-4 grid gap-2">
                {question.options.map((option) => (
                  <label
                    key={option.value}
                    className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm ${answers[question.question_id] === option.value ? "border-graphite bg-graphite text-paper" : "border-graphite/10 bg-mist/45 hover:border-graphite/25"}`}
                  >
                    <input
                      className="sr-only"
                      type="radio"
                      name={`ask-${question.question_id}`}
                      value={option.value}
                      checked={answers[question.question_id] === option.value}
                      onClick={() => {
                        if (answers[question.question_id] === option.value) {
                          setIndex(
                            Math.min(index + 1, interaction.questions.length - 1),
                          );
                        }
                      }}
                      onChange={() => {
                        setAnswers((previous) => ({
                          ...previous,
                          [question.question_id]: option.value,
                        }));
                        setIndex(
                          Math.min(index + 1, interaction.questions.length - 1),
                        );
                      }}
                    />
                    <span className="size-4 rounded-full border" />
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
            </>
          )}
        </fieldset>
      </div>
      <footer className="flex items-center justify-between gap-3 border-t border-graphite/8 bg-mist/60 px-4 py-3">
        <nav className="flex items-center gap-2" aria-label="问题翻页">
          <button
            type="button"
            aria-label="上一题"
            disabled={disabled || index === 0}
            onClick={() => setIndex(index - 1)}
            className="grid size-11 place-items-center rounded-full border border-graphite/10 disabled:opacity-35"
          >
            <ChevronLeft size={18} />
          </button>
          <span className="min-w-10 text-center text-xs tabular-nums">
            {index + 1} / {interaction.questions.length}
          </span>
          <button
            type="button"
            aria-label="下一题"
            disabled={disabled || index >= interaction.questions.length - 1}
            onClick={() => setIndex(index + 1)}
            className="grid size-11 place-items-center rounded-full border border-graphite/10 disabled:opacity-35"
          >
            <ChevronRight size={18} />
          </button>
        </nav>
        <button
          type="button"
          disabled={disabled || !allAnswered}
          onClick={() => submit({ ...answers })}
          className="min-h-11 rounded-full bg-graphite px-4 py-2 text-sm font-semibold text-paper disabled:opacity-35"
        >
          Continue
        </button>
      </footer>
    </article>
  );
}
