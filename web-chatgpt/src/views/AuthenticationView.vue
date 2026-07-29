<script setup lang="ts">
import { computed, ref, watch } from "vue"
import {
  ArrowLeft,
  ArrowRight,
  CircleCheck,
  LockKeyhole,
  Mail,
} from "@lucide/vue"
import { RouterLink } from "vue-router"

import logoUrl from "@/assets/logo.svg"

type AuthenticationMode = "login" | "register"

const props = defineProps<{
  mode: AuthenticationMode
}>()

const email = ref("")
const password = ref("")
const confirmPassword = ref("")
const errorMessage = ref("")
const previewMessage = ref("")

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const isRegister = computed(() => props.mode === "register")
const title = computed(() => (isRegister.value ? "创建账号" : "欢迎回来"))
const description = computed(() =>
  isRegister.value ? "使用邮箱注册 OpenGPT" : "使用邮箱登录 OpenGPT",
)
const alternatePath = computed(() => (isRegister.value ? "/login" : "/register"))
const alternateLead = computed(() =>
  isRegister.value ? "已经有账号？" : "还没有账号？",
)
const alternateAction = computed(() =>
  isRegister.value ? "去登录" : "创建账号",
)

function clearFeedback() {
  errorMessage.value = ""
  previewMessage.value = ""
}

function submitPreview() {
  clearFeedback()

  if (!emailPattern.test(email.value.trim())) {
    errorMessage.value = "请输入有效的邮箱地址。"
    return
  }

  if (password.value.length < 6) {
    errorMessage.value = "密码至少需要 6 位。"
    return
  }

  if (isRegister.value && password.value !== confirmPassword.value) {
    errorMessage.value = "两次输入的密码不一致。"
    return
  }

  previewMessage.value = "界面验证完成，接口将在下一阶段接入。"
}

watch(
  () => props.mode,
  () => {
    email.value = ""
    password.value = ""
    confirmPassword.value = ""
    clearFeedback()
  },
)
</script>

<template>
  <div class="authentication-view">
    <header class="authentication-header">
      <RouterLink
        class="authentication-brand"
        to="/"
        aria-label="OpenGPT 首页"
      >
        <img
          class="authentication-logo"
          :src="logoUrl"
          alt=""
          aria-hidden="true"
        >
        <span class="authentication-brand-name">OpenGPT</span>
      </RouterLink>
    </header>

    <main class="authentication-main">
      <section
        class="authentication-content"
        :aria-labelledby="`auth-${props.mode}-title`"
      >
        <div class="authentication-heading">
          <h1
            :id="`auth-${props.mode}-title`"
            class="authentication-title"
          >
            {{ title }}
          </h1>
          <p class="authentication-description">
            {{ description }}
          </p>
        </div>

        <form
          class="authentication-form"
          novalidate
          @submit.prevent="submitPreview"
        >
          <label class="authentication-field">
            <span class="authentication-field-label">邮箱</span>
            <span class="authentication-control">
              <Mail
                class="authentication-control-icon"
                aria-hidden="true"
                :size="17"
                :stroke-width="1.7"
              />
              <input
                v-model="email"
                class="authentication-input"
                autocomplete="email"
                inputmode="email"
                name="email"
                placeholder="name@example.com"
                required
                type="email"
                @input="clearFeedback"
              >
            </span>
          </label>

          <label class="authentication-field">
            <span class="authentication-field-label">密码</span>
            <span class="authentication-control">
              <LockKeyhole
                class="authentication-control-icon"
                aria-hidden="true"
                :size="17"
                :stroke-width="1.7"
              />
              <input
                v-model="password"
                class="authentication-input"
                :autocomplete="isRegister ? 'new-password' : 'current-password'"
                name="password"
                placeholder="至少 6 位"
                required
                type="password"
                @input="clearFeedback"
              >
            </span>
          </label>

          <label
            v-if="isRegister"
            class="authentication-field"
          >
            <span class="authentication-field-label">确认密码</span>
            <span class="authentication-control">
              <LockKeyhole
                class="authentication-control-icon"
                aria-hidden="true"
                :size="17"
                :stroke-width="1.7"
              />
              <input
                v-model="confirmPassword"
                class="authentication-input"
                autocomplete="new-password"
                name="confirmPassword"
                placeholder="再次输入密码"
                required
                type="password"
                @input="clearFeedback"
              >
            </span>
          </label>

          <p
            v-if="errorMessage"
            class="authentication-feedback is-error"
            role="alert"
          >
            {{ errorMessage }}
          </p>

          <p
            v-if="previewMessage"
            class="authentication-feedback is-preview"
            role="status"
          >
            <CircleCheck
              class="authentication-feedback-icon"
              aria-hidden="true"
              :size="17"
              :stroke-width="1.8"
            />
            <span class="authentication-feedback-message">
              {{ previewMessage }}
            </span>
          </p>

          <button
            class="authentication-submit"
            type="submit"
          >
            <span class="authentication-submit-label">继续</span>
            <ArrowRight
              class="authentication-submit-icon"
              aria-hidden="true"
              :size="18"
              :stroke-width="1.8"
            />
          </button>
        </form>

        <p class="authentication-alternate">
          <span class="authentication-alternate-lead">
            {{ alternateLead }}
          </span>
          <RouterLink
            class="authentication-alternate-link"
            :to="alternatePath"
          >
            {{ alternateAction }}
          </RouterLink>
        </p>
      </section>
    </main>

    <footer class="authentication-footer">
      <RouterLink
        class="authentication-home-link"
        to="/"
      >
        <ArrowLeft
          class="authentication-home-icon"
          aria-hidden="true"
          :size="15"
          :stroke-width="1.8"
        />
        <span class="authentication-home-label">返回聊天</span>
      </RouterLink>
      <span class="authentication-service-status">账号服务尚未连接</span>
    </footer>
  </div>
</template>

<style scoped>
@reference "../styles/index.css";

.authentication-view {
  @apply flex min-h-svh flex-col;

  color: var(--color-text);
  background: var(--color-surface);
}

.authentication-header {
  @apply flex items-center px-6;

  min-height: 74px;
  padding-top: 18px;
  padding-bottom: 18px;
}

.authentication-brand {
  @apply inline-flex items-center gap-2 text-base font-bold no-underline;

  font-family: var(--font-utility);
}

.authentication-logo {
  @apply object-contain;

  width: 30px;
  height: 30px;
}

.authentication-main {
  @apply flex w-full flex-1 items-center justify-center px-5;

  padding-top: 2rem;
  padding-bottom: 72px;
}

.authentication-content {
  @apply w-full;

  max-width: 27rem;
}

.authentication-heading {
  margin-bottom: 2.25rem;
}

.authentication-title {
  @apply m-0 font-semibold;

  font-size: clamp(2rem, 5vw, 2.4rem);
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.authentication-description {
  @apply mb-0;

  margin-top: 1rem;
  color: var(--color-text-muted);
  font-size: 0.88rem;
  line-height: 1.75rem;
}

.authentication-form {
  @apply grid;

  gap: 1.15rem;
}

.authentication-field {
  @apply grid text-xs font-semibold;

  gap: 0.55rem;
}

.authentication-control {
  @apply flex items-center gap-3 border;

  min-height: 3.15rem;
  padding-inline: 0.95rem;
  border-color: var(--color-border-control);
  border-radius: 0.7rem;
  color: var(--color-text-muted);
  background: var(--color-surface-muted);
  transition:
    border-color 150ms ease,
    background-color 150ms ease;
}

.authentication-control:focus-within {
  border-color: var(--color-focus-ring);
  background: var(--color-surface);
}

.authentication-input {
  @apply w-full min-w-0 border-0 bg-transparent outline-none;

  color: var(--color-text);
  font-size: 0.9rem;
}

.authentication-input::placeholder {
  color: var(--color-text-muted);
  opacity: 0.7;
}

.authentication-input:focus-visible {
  outline: none;
}

.authentication-feedback {
  @apply m-0;

  font-size: 0.78rem;
  line-height: 1.55;
}

.authentication-feedback.is-error {
  color: var(--color-danger);
}

.authentication-feedback.is-preview {
  @apply flex items-start;

  gap: 0.6rem;
  padding: 0.85rem 0.9rem;
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: var(--color-surface-muted);
}

.authentication-feedback-icon {
  @apply shrink-0;

  margin-top: 0.08rem;
  color: var(--color-action-primary);
}

.authentication-submit {
  @apply flex items-center justify-between font-semibold;

  min-height: 3.15rem;
  margin-top: 0.2rem;
  padding-inline: 1.05rem;
  border-radius: 0.7rem;
  color: var(--color-on-action);
  background: var(--color-action-primary);
  font-size: 0.86rem;
  transition: background-color 150ms ease;
}

.authentication-submit:hover {
  background: var(--color-action-primary-hover);
}

.authentication-alternate {
  @apply mb-0 flex flex-wrap;

  gap: 0.4rem;
  margin-top: 1.5rem;
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.authentication-alternate-link {
  @apply font-semibold underline;

  border-radius: 0.25rem;
  color: var(--color-action-primary);
  text-underline-offset: 0.2rem;
}

.authentication-footer {
  @apply flex items-center justify-center px-6 text-xs;

  min-height: 58px;
  gap: 0.55rem;
  padding-top: 0.75rem;
  padding-bottom: 18px;
  color: var(--color-text-muted);
}

.authentication-home-link {
  @apply inline-flex items-center gap-2 no-underline;
}

.authentication-home-link:hover {
  color: var(--color-text);
}

@media (max-width: 520px) {
  .authentication-header {
    @apply justify-center;
  }

  .authentication-heading {
    margin-bottom: 1.75rem;
  }

  .authentication-control,
  .authentication-submit {
    min-height: 3.25rem;
  }

  .authentication-footer {
    @apply flex-wrap;
  }
}

@media (prefers-reduced-motion: reduce) {
  .authentication-control,
  .authentication-submit {
    transition: none;
  }
}
</style>
