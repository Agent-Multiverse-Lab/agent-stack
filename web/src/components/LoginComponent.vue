<script setup lang="ts">
import { computed, reactive, ref } from "vue"
import {
  Alert as AAlert,
  Button as AButton,
  ConfigProvider as AConfigProvider,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputPassword as AInputPassword,
  type FormInstance
} from "ant-design-vue"
import type { Rule } from "ant-design-vue/es/form"

import { Lock, Mail } from "@lucide/vue"

import { useAuthStore } from "@/stores/useAuthStore"

interface AuthFormModel {
  email: string
  password: string
  confirmPassword: string
}

const emit = defineEmits<{
  authenticated: []
}>()

const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const form = reactive<AuthFormModel>({
  email: "",
  password: "",
  confirmPassword: ""
})
const isRegister = ref(false)
const submitting = ref(false)
const requestError = ref("")
const registrationComplete = ref(false)

const title = computed(() =>
  isRegister.value ? "Create your account" : "Welcome back"
)
const description = computed(() =>
  isRegister.value
    ? "Create an AU account with your email."
    : "Sign in to AU with your email."
)

const validatePasswordConfirmation = (_rule: Rule, value: string) =>
  value === form.password
    ? Promise.resolve()
    : Promise.reject("Passwords do not match")

const rules: Record<keyof AuthFormModel, Rule[]> = {
  email: [
    { required: true, message: "Enter your email" },
    { type: "email", message: "Enter a valid email" }
  ],
  password: [
    { required: true, message: "Enter your password" },
    { min: 6, max: 128, message: "Use 6 to 128 characters" }
  ],
  confirmPassword: [
    { required: true, message: "Confirm your password" },
    { validator: validatePasswordConfirmation, trigger: "change" }
  ]
}

const authTheme = {
  token: {
    colorPrimary: "#15545a",
    colorText: "#10272b",
    colorTextPlaceholder: "#748386",
    colorBorder: "#cbd6d5",
    borderRadius: 12,
    controlHeightLG: 44,
    fontSizeLG: 14,
    fontFamily: "var(--font-sans)"
  }
}

const clearFeedback = () => {
  requestError.value = ""
  registrationComplete.value = false
}

const showRegister = () => {
  clearFeedback()
  isRegister.value = true
}

const showLogin = () => {
  isRegister.value = false
  form.confirmPassword = ""
  requestError.value = ""
  formRef.value?.clearValidate("confirmPassword")
}

const onBeforeEnter = (el: Element) => {
  const htmlEl = el as HTMLElement
  htmlEl.style.height = "0px"
  htmlEl.style.opacity = "0"
  htmlEl.style.transform = "translateY(-12px)"
  htmlEl.style.transition =
    "height 520ms cubic-bezier(0.22, 1, 0.36, 1), opacity 420ms cubic-bezier(0.22, 1, 0.36, 1), transform 520ms cubic-bezier(0.22, 1, 0.36, 1)"
}

const onEnter = (el: Element) => {
  const htmlEl = el as HTMLElement
  htmlEl.getBoundingClientRect()
  htmlEl.style.height = `${htmlEl.scrollHeight}px`
  htmlEl.style.opacity = "1"
  htmlEl.style.transform = "translateY(0)"
}

const onAfterEnter = (el: Element) => {
  const htmlEl = el as HTMLElement
  htmlEl.style.height = "auto"
}

const onBeforeLeave = (el: Element) => {
  const htmlEl = el as HTMLElement
  htmlEl.style.height = `${htmlEl.scrollHeight}px`
  htmlEl.style.opacity = "1"
  htmlEl.style.transform = "translateY(0)"
  htmlEl.style.transition =
    "height 460ms cubic-bezier(0.22, 1, 0.36, 1), opacity 360ms cubic-bezier(0.22, 1, 0.36, 1), transform 460ms cubic-bezier(0.22, 1, 0.36, 1)"
}

const onLeave = (el: Element) => {
  const htmlEl = el as HTMLElement
  htmlEl.getBoundingClientRect()
  htmlEl.style.height = "0px"
  htmlEl.style.opacity = "0"
  htmlEl.style.transform = "translateY(-12px)"
}

const onAfterLeave = (el: Element) => {
  const htmlEl = el as HTMLElement
  htmlEl.style.height = ""
}

const submit = async () => {
  clearFeedback()
  submitting.value = true

  const payload = {
    email: form.email.trim().toLowerCase(),
    password: form.password
  }

  try {
    if (isRegister.value) {
      await authStore.register(payload)
      form.confirmPassword = ""
      formRef.value?.clearValidate("confirmPassword")
      isRegister.value = false
      registrationComplete.value = true
      return
    }

    await authStore.login(payload)
    emit("authenticated")
  } catch (error) {
    requestError.value =
      error instanceof Error ? error.message : "Authentication failed"
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AConfigProvider :theme="authTheme">
    <section
      class="w-full max-w-[310px]"
      aria-labelledby="authentication-title"
    >
      <div class="mb-7">
        <h1
          id="authentication-title"
          class="m-0 text-[32px] leading-[1.1] font-bold tracking-[-0.03em] text-[#10272b]"
        >
          {{ title }}
        </h1>
        <p class="mb-0 mt-2 text-[14px] leading-5 text-[#66777a]">
          {{ description }}
        </p>
      </div>

      <AForm
        ref="formRef"
        :model="form"
        :rules="rules"
        layout="vertical"
        size="large"
        :required-mark="false"
        @finish="submit"
      >
        <AFormItem class="mb-4!" name="email">
          <AInput
            v-model:value="form.email"
            autocomplete="email"
            inputmode="email"
            :maxlength="255"
            name="email"
            placeholder="Enter your email"
            type="email"
            aria-label="Email"
            :disabled="submitting"
            @input="clearFeedback"
          >
            <template #prefix>
              <Mail class="mr-1.5 h-4 w-4 text-[#748386]" aria-hidden="true" />
            </template>
          </AInput>
        </AFormItem>

        <AFormItem class="mb-4!" name="password">
          <AInputPassword
            v-model:value="form.password"
            :autocomplete="isRegister ? 'new-password' : 'current-password'"
            :maxlength="128"
            name="password"
            placeholder="Enter your password"
            aria-label="Password"
            :disabled="submitting"
            @input="clearFeedback"
          >
            <template #prefix>
              <Lock class="mr-1.5 h-4 w-4 text-[#748386]" aria-hidden="true" />
            </template>
          </AInputPassword>
        </AFormItem>

        <Transition
          :css="false"
          @before-enter="onBeforeEnter"
          @enter="onEnter"
          @after-enter="onAfterEnter"
          @before-leave="onBeforeLeave"
          @leave="onLeave"
          @after-leave="onAfterLeave"
        >
          <div v-if="isRegister" class="overflow-hidden">
            <AFormItem class="mb-4!" name="confirmPassword">
              <AInputPassword
                v-model:value="form.confirmPassword"
                autocomplete="new-password"
                autofocus
                :maxlength="128"
                name="confirmPassword"
                placeholder="Ensure your password"
                aria-label="Ensure your password"
                :disabled="submitting"
                @input="clearFeedback"
              >
                <template #prefix>
                  <Lock class="mr-1.5 h-4 w-4 text-[#748386]" aria-hidden="true" />
                </template>
              </AInputPassword>
            </AFormItem>
          </div>
        </Transition>

        <AAlert
          v-if="registrationComplete"
          class="mb-4"
          message="Account created successfully. Please log in."
          show-icon
          type="success"
        />
        <AAlert
          v-else-if="requestError"
          class="mb-4"
          :message="requestError"
          show-icon
          type="error"
        />

        <div class="mt-2 grid gap-4">
          <AButton
            class="h-[44px]! w-full text-base! font-semibold! shadow-[0_6px_16px_rgba(21,84,90,0.18)]!"
            block
            html-type="submit"
            :loading="submitting"
            size="large"
            type="primary"
          >
            {{ isRegister ? "Create Account" : "Sign In" }}
          </AButton>

          <div class="text-center text-sm text-[#66777a]">
            <template v-if="isRegister">
              Already have an account?
              <button
                type="button"
                class="ml-1 font-semibold text-[#15545a] hover:underline focus:outline-none"
                :disabled="submitting"
                @click="showLogin"
              >
                Log in
              </button>
            </template>
            <template v-else>
              Don't have an account?
              <button
                type="button"
                class="ml-1 font-semibold text-[#15545a] hover:underline focus:outline-none"
                :disabled="submitting"
                @click="showRegister"
              >
                Create one
              </button>
            </template>
          </div>
        </div>
      </AForm>
    </section>
  </AConfigProvider>
</template>
