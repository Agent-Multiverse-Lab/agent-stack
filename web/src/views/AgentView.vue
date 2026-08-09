<script setup lang="ts">
import { Bot } from "@lucide/vue"
</script>

<template>
  <main
    class="flex h-full min-h-0 w-full items-center justify-center bg-paper px-5 pb-[6rem] text-graphite"
    aria-label="Agent"
  >
    <section
      class="flex w-full max-w-[30rem] flex-col items-center text-center"
      aria-labelledby="agent-heading"
    >
      <Bot
        class="mb-4 text-graphite"
        :size="44"
        :stroke-width="1.35"
        aria-hidden="true"
      />
      <p class="m-0 mb-3 inline-flex items-center gap-2 font-utility text-[0.66rem] uppercase tracking-[0.04em] text-graphite/58">
        <span class="h-[5px] w-[5px] rounded-full bg-graphite/58" aria-hidden="true" />
        <span>Backend not connected</span>
      </p>
      <h2
        id="agent-heading"
        class="m-0 text-[clamp(1.6rem,4vw,2rem)] font-[550] leading-[1.25] tracking-[-0.035em]"
      >
        Agent setup is not connected
      </h2>
      <p class="m-0 mt-3 max-w-[27rem] text-sm leading-[1.625] text-slate">
        Agent configuration will be available here after the backend is connected.
      </p>
    </section>
  </main>
</template>
