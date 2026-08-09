import { ref } from "vue"
import { defineStore } from "pinia"

import { getCurrentUser, loginUser, registerUser } from "@/api/auth"
import type {
  LoginRequest,
  RegisterRequest,
  UserResponse
} from "@/types/auth"

const ACCESS_TOKEN_STORAGE_KEY = "au.access_token"

export const useAuthStore = defineStore("auth", () => {
  const accessToken = ref<string | null>(
    localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
  )
  const user = ref<UserResponse | null>(null)

  const logout = () => {
    accessToken.value = null
    user.value = null
    localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
  }

  const restore = async () => {
    const storedToken = accessToken.value
    if (!storedToken) return

    try {
      const currentUser = await getCurrentUser(storedToken)
      if (accessToken.value === storedToken) user.value = currentUser
    } catch {
      if (accessToken.value === storedToken) logout()
    }
  }

  const login = async (payload: LoginRequest) => {
    const response = await loginUser(payload)
    accessToken.value = response.access_token
    user.value = response.user
    localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, response.access_token)
  }

  const register = (payload: RegisterRequest) => registerUser(payload)

  void restore()

  return { accessToken, user, login, register, logout }
})
