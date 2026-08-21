const ACCESS_TOKEN_STORAGE_KEY = "au.access_token"

export const getAccessToken = () =>
  localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)

export const saveAccessToken = (accessToken: string) =>
  localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken)

export const clearAccessToken = () =>
  localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
