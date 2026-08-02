<script setup lang="ts">
import type { Component } from "vue"
import { computed } from "vue"
import {
  Bot,
  Image as ImageIcon,
  Layers,
  Library,
  SquareTerminal
} from "@lucide/vue"

import type { FeatureId } from "@/types/feature"

const props = defineProps<{
  featureId: FeatureId
}>()

const features: Record<
  FeatureId,
  {
    title: string
    headline: string
    description: string
    icon: Component
  }
> = {
  library: {
    title: "Library",
    headline: "Nothing saved yet",
    description: "Saved content will appear here after Library data is connected.",
    icon: Library
  },
  agent: {
    title: "Agent",
    headline: "Agent setup is not connected",
    description:
      "Agent configuration will be available here after the backend is connected.",
    icon: Bot
  },
  image: {
    title: "Image",
    headline: "No images yet",
    description:
      "Generated images will appear here after image generation is connected.",
    icon: ImageIcon
  },
  static: {
    title: "Static",
    headline: "Static is not connected",
    description:
      "Static content will be available here after the backend is connected.",
    icon: Layers
  },
  sandbox: {
    title: "Sandbox",
    headline: "Sandbox is not connected",
    description:
      "Sandbox sessions will appear here after runtime services are connected.",
    icon: SquareTerminal
  }
}

const feature = computed(() => features[props.featureId])
</script>

<template>
  <main
    class="unavailable-feature-view"
    :aria-label="feature.title"
  >
    <section
      class="unavailable-feature-content"
      :aria-labelledby="`${props.featureId}-heading`"
    >
      <component
        :is="feature.icon"
        class="unavailable-feature-icon"
        :size="44"
        :stroke-width="1.35"
        aria-hidden="true"
      />
      <p class="unavailable-feature-status">
        <span
          class="unavailable-feature-status-dot"
          aria-hidden="true"
        />
        <span class="unavailable-feature-status-label">
          Backend not connected
        </span>
      </p>
      <h2
        :id="`${props.featureId}-heading`"
        class="unavailable-feature-title"
      >
        {{ feature.headline }}
      </h2>
      <p class="unavailable-feature-description">
        {{ feature.description }}
      </p>
    </section>
  </main>
</template>

<style scoped>
@reference "../styles/index.css";

.unavailable-feature-view {
  @apply flex h-full min-h-0 w-full items-center justify-center px-5;

  padding-bottom: 6rem;
  color: var(--color-text);
  background: var(--color-canvas);
}

.unavailable-feature-content {
  @apply flex w-full flex-col items-center text-center;

  max-width: 30rem;
}

.unavailable-feature-icon {
  margin-bottom: 1rem;
  color: var(--color-text);
}

.unavailable-feature-status {
  @apply inline-flex items-center uppercase;

  gap: 0.5rem;
  margin: 0 0 0.75rem;
  color: var(--color-text-subtle);
  font-family: var(--font-utility);
  font-size: 0.66rem;
  letter-spacing: 0.04em;
}

.unavailable-feature-status-dot {
  @apply rounded-full;

  width: 5px;
  height: 5px;
  background: var(--color-text-subtle);
}

.unavailable-feature-title {
  @apply m-0;

  font-size: clamp(1.6rem, 4vw, 2rem);
  font-weight: 550;
  line-height: 1.25;
  letter-spacing: -0.035em;
}

.unavailable-feature-description {
  @apply text-sm;

  max-width: 27rem;
  margin: 0.75rem 0 0;
  color: var(--color-text-muted);
  line-height: 1.625;
}
</style>
