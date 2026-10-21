import { apiClient } from "@/api/client"

export interface RegisterRequest {
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface UserResponse {
  id: number
  uid: string
  email: string
  is_active: boolean
  is_admin: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserResponse
}

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
