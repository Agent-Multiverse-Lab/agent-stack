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
  let validatedToken: string | null = null
  let restorePromise: Promise<boolean> | null = null

  const isExpired = (token: string) => {
    try {
      const payload = JSON.parse(
        atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))
      ) as { exp?: unknown }
      return typeof payload.exp === "number" && payload.exp * 1000 <= Date.now()
    } catch {
      return false
    }
  }

  const logout = () => {
    accessToken.value = null
    user.value = null
    validatedToken = null
    clearAccessToken()
  }

  const restore = async () => {
    const storedToken = accessToken.value
    if (!storedToken) return false
    if (isExpired(storedToken)) {
      logout()
      return false
    }
    if (validatedToken === storedToken && user.value) return true
    if (restorePromise) return restorePromise

    const request = (async () => {
      try {
        const currentUser = await getCurrentUser()
        if (accessToken.value !== storedToken) return false
        user.value = currentUser
        validatedToken = storedToken
        return true
      } catch {
        if (accessToken.value === storedToken) logout()
        return false
      }
    })()
    restorePromise = request
    try {
      return await request
    } finally {
      if (restorePromise === request) restorePromise = null
    }
  }

  const login = async (payload: LoginRequest) => {
    const response = await loginUser(payload)
    accessToken.value = response.access_token
    user.value = response.user
    validatedToken = response.access_token
    saveAccessToken(response.access_token)
  }

  const register = (payload: RegisterRequest) => registerUser(payload)

  return { accessToken, user, login, register, logout, restore }
})
