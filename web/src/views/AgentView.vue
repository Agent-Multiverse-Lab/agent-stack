<script setup lang="ts">
import { Bot } from "@lucide/vue"
</script>

<template>
  <main class="agent-view" aria-label="Agent">
    <section class="feature-view-content" aria-labelledby="agent-heading">
      <Bot class="feature-view-icon" :size="44" :stroke-width="1.35" aria-hidden="true" />
      <p class="feature-view-status">
        <span class="feature-view-status-dot" aria-hidden="true" />
        <span>Backend not connected</span>
      </p>
      <h2 id="agent-heading" class="feature-view-title">
        Agent setup is not connected
      </h2>
      <p class="feature-view-description">
        Agent configuration will be available here after the backend is connected.
      </p>
    </section>
  </main>
</template>

<style scoped>
@reference "../styles/index.css";

.agent-view {
  @apply flex h-full min-h-0 w-full items-center justify-center px-5;
  padding-bottom: 6rem;
  color: var(--color-text);
  background: var(--color-canvas);
}

.feature-view-content {
  @apply flex w-full flex-col items-center text-center;
  max-width: 30rem;
}

.feature-view-icon {
  margin-bottom: 1rem;
  color: var(--color-text);
}

.feature-view-status {
  @apply inline-flex items-center uppercase;
  gap: 0.5rem;
  margin: 0 0 0.75rem;
  color: var(--color-text-subtle);
  font-family: var(--font-utility);
  font-size: 0.66rem;
  letter-spacing: 0.04em;
}

.feature-view-status-dot {
  @apply rounded-full;
  width: 5px;
  height: 5px;
  background: var(--color-text-subtle);
}

.feature-view-title {
  @apply m-0;
  font-size: clamp(1.6rem, 4vw, 2rem);
  font-weight: 550;
  line-height: 1.25;
  letter-spacing: -0.035em;
}

.feature-view-description {
  @apply text-sm;
  max-width: 27rem;
  margin: 0.75rem 0 0;
  color: var(--color-text-muted);
  line-height: 1.625;
}
</style>
