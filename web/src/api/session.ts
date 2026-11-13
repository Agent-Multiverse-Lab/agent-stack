const ACCESS_TOKEN_STORAGE_KEY = "au.access_token"

/**
 * 从 localStorage 读取当前保存的访问令牌。
 * @returns 访问令牌字符串，未登录时返回 null。
 */
export const getAccessToken = () =>
  localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)

/**
 * 将访问令牌持久化到 localStorage。
 * @param accessToken 登录返回的 JWT 访问令牌。
 */
export const saveAccessToken = (accessToken: string) =>
  localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken)

/**
 * 清除 localStorage 中保存的访问令牌。
 */
export const clearAccessToken = () =>
  localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
