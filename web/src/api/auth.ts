import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse
} from "@/types/auth"

const readError = async (response: Response) => {
  const payload = (await response.json().catch(() => null)) as {
    detail?: unknown
  } | null
  return typeof payload?.detail === "string"
    ? payload.detail
    : `请求失败（${response.status}）`
}

const requestJson = async <T>(
  path: string,
  payload: LoginRequest | RegisterRequest
): Promise<T> => {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<T>
}

export const registerUser = (payload: RegisterRequest) =>
  requestJson<UserResponse>("/api/auth/register", payload)

export const loginUser = (payload: LoginRequest) =>
  requestJson<TokenResponse>("/api/auth/login", payload)

export const getCurrentUser = async (accessToken: string) => {
  const response = await fetch("/api/auth/me", {
    headers: { Authorization: `Bearer ${accessToken}` }
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<UserResponse>
}
