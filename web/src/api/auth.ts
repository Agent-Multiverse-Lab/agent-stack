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

/**
 * 注册新用户账号。
 * @param payload 注册邮箱与密码。
 * @returns 新创建的用户信息。
 */
export const registerUser = (payload: RegisterRequest) =>
  apiClient.apiPost<UserResponse, RegisterRequest>(
    "/api/auth/register",
    payload,
    { requiresAuth: false }
  )

/**
 * 使用邮箱和密码登录并获取访问令牌。
 * @param payload 登录邮箱与密码。
 * @returns 访问令牌与当前用户信息。
 */
export const loginUser = (payload: LoginRequest) =>
  apiClient.apiPost<TokenResponse, LoginRequest>(
    "/api/auth/login",
    payload,
    { requiresAuth: false }
  )

/**
 * 获取当前已登录用户的个人资料。
 * @returns 当前用户基本信息与权限标记。
 */
export const getCurrentUser = () =>
  apiClient.apiGet<UserResponse>("/api/auth/me", {
    requiresAuth: true
  })
