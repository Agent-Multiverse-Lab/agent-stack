import type { FormEvent } from "react";
import { useTranslation } from "@/i18n";

import {
  Questionnaire,
  QuestionnaireActions,
  QuestionnaireChoice,
  QuestionnaireChoices,
  QuestionnaireError,
  QuestionnaireItem,
  QuestionnaireNext,
  QuestionnairePrevious,
  QuestionnaireProgress,
  QuestionnaireSubmit,
  QuestionnaireTitle,
} from "@/components/ui/questionnaire";
import type { InteractionRequired } from "@/pages/chat/types";

interface AskUserProps {
  interaction: InteractionRequired;
  disabled?: boolean;
  submit: (answers: Record<string, string>) => void;
}

export function AskUser({ interaction, disabled = false, submit }: AskUserProps) {
  const { t } = useTranslation();
  if (interaction.questions.length === 0) return null;

  const items = interaction.questions.map((question) => ({
    name: question.question_id,
    required: true,
    choices: question.options.map(({ value }) => ({ value })),
  }));

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const answers: Record<string, string> = {};

    for (const question of interaction.questions) {
      const value = formData.get(question.question_id);
      if (
        typeof value !== "string" ||
        !question.options.some((option) => option.value === value)
      ) {
        return;
      }
      answers[question.question_id] = value;
    }

    submit(answers);
  }

  return (
    <article
      aria-label={t("Agent questions")}
      className="w-full overflow-hidden rounded-[1.4rem] border border-border bg-card shadow-[0_2px_8px_rgb(0_0_0/0.05)]"
    >
      <Questionnaire
        className="relative gap-3 px-4 pt-4 pb-3"
        defaultItem={interaction.questions[0].question_id}
        items={items}
        shortcuts="letters"
        onSubmit={handleSubmit}
      >
        <QuestionnaireProgress
          className="absolute top-4 right-5 text-right"
          render={(props, state) => (
            <div
              {...props}
              aria-label={t("Questionnaire progress")}
              aria-valuetext={t("Question {{current}} of {{total}}", state)}
            >
              {t("Question {{current}} of {{total}}", state)}
            </div>
          )}
        />

        {interaction.questions.map((question) => (
          <QuestionnaireItem
            key={question.question_id}
            name={question.question_id}
            required
            disabled={disabled}
            className="max-h-[min(18rem,40dvh)] gap-3 overflow-y-auto px-1"
          >
            <QuestionnaireTitle className="[&:not(:has(~[data-slot=questionnaire-description]))]:mb-3 pr-28 text-[15px] leading-snug font-semibold text-foreground">
              {question.question}
            </QuestionnaireTitle>
            <QuestionnaireChoices>
              {question.options.map((option) => (
                <QuestionnaireChoice key={option.value} value={option.value}>
                  {option.label}
                </QuestionnaireChoice>
              ))}
            </QuestionnaireChoices>
            <QuestionnaireError>
              {t("Choose an answer to continue.")}
            </QuestionnaireError>
          </QuestionnaireItem>
        ))}

        <QuestionnaireActions className="px-1 pt-1">
          <QuestionnairePrevious disabled={disabled}>{t("Previous")}</QuestionnairePrevious>
          <QuestionnaireNext disabled={disabled}>{t("Next")}</QuestionnaireNext>
          <QuestionnaireSubmit disabled={disabled}>{t("Continue")}</QuestionnaireSubmit>
        </QuestionnaireActions>
      </Questionnaire>
    </article>
  );
}
