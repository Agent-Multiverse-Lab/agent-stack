<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from "vue"
import { X } from "@lucide/vue"

import UserAvatarComponent from "@/components/UserAvatarComponent.vue"
import type { UserResponse } from "@/types/auth"

const props = defineProps<{
  open: boolean
  user: UserResponse | null
  username: string
}>()

const emit = defineEmits<{
  close: []
}>()

const accountStatus = computed(() => {
  if (!props.user) return "Loading"
  return props.user.is_active ? "Active" : "Inactive"
})

const close = () => emit("close")

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === "Escape") close()
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      document.addEventListener("keydown", onKeydown)
      return
    }

    document.removeEventListener("keydown", onKeydown)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-150 ease-out motion-reduce:transition-none"
      leave-active-class="transition-opacity duration-150 ease-in motion-reduce:transition-none"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-[100] grid place-items-end bg-graphite/36 min-[640px]:place-items-center min-[640px]:p-6"
        @mousedown.self="close"
      >
        <section
          class="w-full rounded-t-lg bg-paper text-graphite min-[640px]:max-w-[440px] min-[640px]:rounded-lg"
          role="dialog"
          aria-modal="true"
          aria-labelledby="profile-title"
        >
          <header class="flex min-h-[3.25rem] items-center justify-between gap-4 pt-1 pr-3 pb-1 pl-5">
            <h2 id="profile-title" class="m-0 text-[0.95rem] font-semibold tracking-[-0.02em]">
              Profile
            </h2>

            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-sm bg-transparent text-slate transition-colors duration-150 hover:bg-mist hover:text-graphite motion-reduce:transition-none"
              type="button"
              aria-label="Close profile"
              @click="close"
            >
              <X :size="19" :stroke-width="1.8" aria-hidden="true" />
            </button>
          </header>

          <div class="grid gap-6 px-5 pt-3 pb-6 min-[640px]:px-7 min-[640px]:pb-7">
            <div class="grid justify-items-center gap-3 border-b border-graphite/6 pb-6 text-center">
              <UserAvatarComponent :label="username" size="large" />
              <div class="min-w-0">
                <p class="m-0 truncate font-semibold tracking-[-0.02em]">{{ username }}</p>
                <p class="m-0 mt-1 truncate text-sm text-slate">
                  {{ user?.email ?? "Loading account…" }}
                </p>
              </div>
            </div>

            <dl class="m-0 grid gap-0 text-sm">
              <div class="flex min-h-12 items-center justify-between gap-5 border-b border-graphite/6 py-3">
                <dt>Email</dt>
                <dd class="m-0 min-w-0 truncate text-right text-slate">
                  {{ user?.email ?? "—" }}
                </dd>
              </div>
              <div class="flex min-h-12 items-center justify-between gap-5 py-3">
                <dt>Status</dt>
                <dd class="m-0 text-right text-slate">{{ accountStatus }}</dd>
              </div>
            </dl>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
