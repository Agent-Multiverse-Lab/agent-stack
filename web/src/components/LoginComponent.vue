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
      class="w-full max-w-[280px]"
      aria-labelledby="authentication-title"
    >
      <div class="mb-8">
        <h1
          id="authentication-title"
          class="m-0 text-[30px] leading-[1.08] font-semibold tracking-[-0.04em] text-[#10272b]"
        >
          {{ title }}
        </h1>
        <p class="mb-0 mt-3 text-[13px] leading-5 text-[#66777a]">
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
            placeholder="Email"
            type="email"
            aria-label="Email"
            :disabled="submitting"
            @input="clearFeedback"
          />
        </AFormItem>

        <AFormItem class="mb-4!" name="password">
          <AInputPassword
            v-model:value="form.password"
            :autocomplete="isRegister ? 'new-password' : 'current-password'"
            :maxlength="128"
            name="password"
            placeholder="Password"
            aria-label="Password"
            :disabled="submitting"
            @input="clearFeedback"
          />
        </AFormItem>

        <Transition
          enter-active-class="overflow-hidden transition-[max-height,opacity,transform] duration-[220ms] ease-out motion-reduce:transition-none"
          enter-from-class="max-h-0 -translate-y-1.5 opacity-0"
          enter-to-class="max-h-32 translate-y-0 opacity-100"
          leave-active-class="overflow-hidden transition-[max-height,opacity,transform] duration-[220ms] ease-in motion-reduce:transition-none"
          leave-from-class="max-h-32 translate-y-0 opacity-100"
          leave-to-class="max-h-0 -translate-y-1.5 opacity-0"
        >
          <div v-if="isRegister" class="max-h-32">
            <AFormItem class="mb-4!" name="confirmPassword">
              <AInputPassword
                v-model:value="form.confirmPassword"
                autocomplete="new-password"
                autofocus
                :maxlength="128"
                name="confirmPassword"
                placeholder="Confirm password"
                aria-label="Confirm password"
                :disabled="submitting"
                @input="clearFeedback"
              />
            </AFormItem>
          </div>
        </Transition>

        <AAlert
          v-if="registrationComplete"
          class="mb-4"
          message="Account created. Log in to continue."
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

        <div class="grid gap-3">
          <AButton
            class="h-[42px]! w-full max-w-[240px] justify-self-center text-sm! font-semibold! shadow-[0_6px_16px_rgba(21,84,90,0.20)]!"
            block
            html-type="submit"
            :loading="submitting"
            size="large"
            type="primary"
          >
            {{ isRegister ? "Create Account" : "Login" }}
          </AButton>

          <AButton
            class="h-[42px]! w-full max-w-[240px] justify-self-center text-sm! font-semibold!"
            block
            html-type="button"
            size="large"
            :disabled="submitting"
            @click="isRegister ? showLogin() : showRegister()"
          >
            {{ isRegister ? "Back to Login" : "Create Account" }}
          </AButton>
        </div>
      </AForm>
    </section>
  </AConfigProvider>
</template>
