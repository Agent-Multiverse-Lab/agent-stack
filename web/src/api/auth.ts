import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse
} from "@/types/auth"

import { apiClient } from "@/api/client"

export const registerUser = (payload: RegisterRequest) =>
  apiClient.apiPost<UserResponse, RegisterRequest>(
    "/api/auth/register",
    payload,
    { requiresAuth: false }
  )

export const loginUser = (payload: LoginRequest) =>
  apiClient.apiPost<TokenResponse, LoginRequest>(
    "/api/auth/login",
    payload,
    { requiresAuth: false }
  )

export const getCurrentUser = () =>
  apiClient.apiGet<UserResponse>("/api/auth/me", {
    requiresAuth: true
  })
