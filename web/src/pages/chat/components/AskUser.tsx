import type { FormEvent } from "react";
import { useTranslation } from "@/i18n";

import {
  Questionnaire,
  QuestionnaireActions,
  QuestionnaireChoice,
  QuestionnaireChoices,
  QuestionnaireDescription,
  QuestionnaireError,
  QuestionnaireItem,
  QuestionnaireNext,
  QuestionnairePrevious,
  QuestionnaireProgress,
  QuestionnaireSkip,
  QuestionnaireSubmit,
  QuestionnaireTitle,
} from "@/components/ui/questionnaire";
import type { InteractionRequired } from "@/types/chat";

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
      className="w-full max-w-[36rem] overflow-hidden rounded-[1.25rem] border border-border bg-background shadow-lg"
    >
      <header className="border-b border-border px-5 py-4">
        <p className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
          {t("Input required")}
        </p>
        <h2 className="mt-1 text-base font-semibold text-foreground">
          {t("Agent needs your choice")}
        </h2>
      </header>

      <Questionnaire
        className="gap-0"
        defaultItem={interaction.questions[0].question_id}
        items={items}
        shortcuts="letters"
        onSubmit={handleSubmit}
      >
        <QuestionnaireProgress
          className="px-5 pt-4"
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
            className="h-[min(22rem,45dvh)] overflow-y-auto px-5 py-5"
          >
            <QuestionnaireTitle>{question.question}</QuestionnaireTitle>
            <QuestionnaireDescription>
              {t("Choose an option, then continue. You can go back to change it.")}
            </QuestionnaireDescription>
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

        <QuestionnaireActions className="border-t border-border bg-muted px-4 py-3">
          <QuestionnairePrevious disabled={disabled}>{t("Previous")}</QuestionnairePrevious>
          <QuestionnaireSkip disabled={disabled}>{t("Skip")}</QuestionnaireSkip>
          <QuestionnaireNext disabled={disabled}>{t("Next")}</QuestionnaireNext>
          <QuestionnaireSubmit disabled={disabled}>{t("Continue")}</QuestionnaireSubmit>
        </QuestionnaireActions>
      </Questionnaire>
    </article>
  );
}
