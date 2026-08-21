import { ref } from "vue"
import { defineStore } from "pinia"

import { getCurrentUser, loginUser, registerUser } from "@/api/auth"
import {
  clearAccessToken,
  getAccessToken,
  saveAccessToken
} from "@/api/session"
import type {
  LoginRequest,
  RegisterRequest,
  UserResponse
} from "@/types/auth"

export const useAuthStore = defineStore("auth", () => {
  const accessToken = ref<string | null>(getAccessToken())
  const user = ref<UserResponse | null>(null)

  const logout = () => {
    accessToken.value = null
    user.value = null
    clearAccessToken()
  }

  const restore = async () => {
    const storedToken = accessToken.value
    if (!storedToken) return

    try {
      const currentUser = await getCurrentUser()
      if (accessToken.value === storedToken) user.value = currentUser
    } catch {
      if (accessToken.value === storedToken) logout()
    }
  }

  const login = async (payload: LoginRequest) => {
    const response = await loginUser(payload)
    accessToken.value = response.access_token
    user.value = response.user
    saveAccessToken(response.access_token)
  }

  const register = (payload: RegisterRequest) => registerUser(payload)

  void restore()

  return { accessToken, user, login, register, logout }
})
