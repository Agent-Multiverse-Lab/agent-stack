<script setup lang="ts">
import { GithubOutlined } from "@ant-design/icons-vue"
import { RouterLink, useRouter } from "vue-router"

import authIllustrationUrl from "@/assets/auth-illustrate.png"
import logoUrl from "@/assets/logo.svg"
import LoginComponent from "@/components/LoginComponent.vue"

const router = useRouter()

const openChat = () => router.replace({ name: "chat" })
</script>

<template>
  <main class="relative h-svh overflow-y-auto bg-white text-[#10272b]">
    <header
      class="absolute inset-x-8 top-8 z-10 flex items-center justify-between max-[1000px]:inset-x-4 max-[1000px]:top-4"
      aria-label="Page header"
    >
      <RouterLink
        class="inline-flex min-h-9 items-center gap-2 rounded-lg px-1 text-sm font-bold tracking-[-0.02em] hover:text-[#15545a] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#15545a]"
        :to="{ name: 'chat' }"
        aria-label="AU home"
      >
        <img
          class="size-6 object-contain"
          :src="logoUrl"
          alt=""
          aria-hidden="true"
        >
        <span>AU</span>
      </RouterLink>

      <a
        class="grid size-9 place-items-center rounded-lg text-[#10272b] hover:bg-[#f2f4f3] hover:text-[#15545a] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#15545a]"
        href="https://github.com/leeejuju/multi-agent-s2c"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="AU on GitHub"
      >
        <GithubOutlined class="text-xl" aria-hidden="true" />
      </a>
    </header>

    <div
      class="flex min-h-full items-center justify-center p-6 max-[1000px]:items-start max-[1000px]:px-4 max-[1000px]:pt-20 max-[1000px]:pb-4"
    >
      <section
        class="grid h-[560px] w-full max-w-[900px] grid-cols-[7fr_5fr] overflow-hidden rounded-[16px] bg-[#f2f4f3] shadow-[0_28px_80px_rgba(8,37,43,0.18)] max-[1000px]:h-auto max-[1000px]:grid-cols-1"
        aria-label="AU authentication"
      >
        <div
          class="min-h-0 overflow-hidden max-[1000px]:h-[clamp(240px,48vw,420px)]"
        >
          <img
            class="size-full object-cover object-center"
            :src="authIllustrationUrl"
            alt=""
            aria-hidden="true"
          >
        </div>

        <div
          class="flex min-h-0 min-w-0 overflow-y-auto bg-[#f2f4f3] px-8 py-6 max-[1000px]:px-[clamp(1.5rem,8vw,3rem)] max-[1000px]:py-12"
        >
          <div class="my-auto flex w-full justify-center">
            <LoginComponent @authenticated="openChat" />
          </div>
        </div>
      </section>
    </div>
  </main>
</template>
