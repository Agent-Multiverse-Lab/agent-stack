<template>
  <article
    class="w-full max-w-[25rem] overflow-hidden rounded-[1.25rem] border border-graphite/10 bg-paper shadow-[0_18px_48px_rgba(13,13,13,0.09)]"
    aria-label="Human approval"
  >
    <header class="flex items-center justify-between gap-4 border-b border-graphite/8 px-5 py-4">
      <div class="flex min-w-0 items-center gap-3">
        <span
          class="grid size-9 shrink-0 place-items-center rounded-full bg-graphite text-paper"
          aria-hidden="true"
        >
          <svg
            width="17"
            height="17"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.9"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M12 3 5.5 5.8v5.5c0 4.1 2.7 7.7 6.5 9.2 3.8-1.5 6.5-5.1 6.5-9.2V5.8L12 3Z" />
            <path d="m9.2 11.8 1.8 1.8 3.9-4.1" />
          </svg>
        </span>

        <div class="min-w-0">
          <p class="m-0 font-utility text-[0.66rem] font-bold tracking-[0.12em] text-slate uppercase">
            Human checkpoint
          </p>
          <h2 class="m-0 mt-0.5 truncate text-sm font-semibold tracking-[-0.015em] text-graphite">
            Approval required
          </h2>
        </div>
      </div>

      <div class="shrink-0">
        <slot name="status" />
      </div>
    </header>

    <section class="px-5 py-5" aria-live="polite">
      <div class="text-[0.95rem] font-medium leading-6 text-graphite">
        <slot name="question" />
      </div>

      <div
        class="mt-4 grid gap-2"
        role="group"
        aria-label="Approval options"
      >
        <slot name="options" />
      </div>

      <div class="mt-3">
        <slot name="custom-answer" />
      </div>
    </section>

    <footer class="flex min-h-16 items-center justify-between gap-4 border-t border-graphite/8 bg-mist/70 px-4 py-3">
      <div class="min-w-0 font-utility text-xs text-slate tabular-nums">
        <slot name="progress" />
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <slot name="actions" />
      </div>
    </footer>
  </article>
</template>
