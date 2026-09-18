import { getAccessToken } from "@/api/session"
import i18n from "@/i18n"

export type ApiFetchOptions = RequestInit & {
  requiresAuth: boolean
}

export type ApiRequestOptions = Omit<
  ApiFetchOptions,
  "body" | "method"
>

export interface ApiClient {
  apiFetch(
    path: string,
    options: ApiFetchOptions
  ): Promise<Response>

  apiGet<T>(
    path: string,
    options: ApiRequestOptions
  ): Promise<T>

  apiPost<TResponse, TBody = undefined>(
    path: string,
    body: TBody,
    options: ApiRequestOptions
  ): Promise<TResponse>

  apiDelete<T = void>(
    path: string,
    options: ApiRequestOptions
  ): Promise<T>
}

export class FetchApiClient implements ApiClient {
  async apiFetch(
    path: string,
    options: ApiFetchOptions
  ): Promise<Response> {
    const { requiresAuth, ...init } = options
    const headers = new Headers(init.headers)

    if (requiresAuth) {
      const accessToken = getAccessToken()
      if (!accessToken) throw new Error(i18n.t("Please log in to continue"))
      headers.set("Authorization", `Bearer ${accessToken}`)
    }

    const response = await fetch(path, { ...init, headers })
    if (!response.ok) throw new Error(await this.readApiError(response))
    return response
  }

  async apiGet<T>(
    path: string,
    options: ApiRequestOptions
  ): Promise<T> {
    const response = await this.apiFetch(path, {
      ...options,
      method: "GET"
    })
    return this.readResponse<T>(response)
  }

  async apiPost<TResponse, TBody = undefined>(
    path: string,
    body: TBody,
    options: ApiRequestOptions
  ): Promise<TResponse> {
    const headers = new Headers(options.headers)
    let requestBody: BodyInit | undefined

    if (body instanceof FormData) {
      requestBody = body
    } else if (body !== undefined) {
      headers.set("Content-Type", "application/json")
      requestBody = JSON.stringify(body)
    }

    const response = await this.apiFetch(path, {
      ...options,
      method: "POST",
      headers,
      body: requestBody
    })
    return this.readResponse<TResponse>(response)
  }

  async apiDelete<T = void>(
    path: string,
    options: ApiRequestOptions
  ): Promise<T> {
    const response = await this.apiFetch(path, {
      ...options,
      method: "DELETE"
    })
    return this.readResponse<T>(response)
  }

  protected async readApiError(response: Response) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: unknown
    } | null
    return typeof payload?.detail === "string"
      ? payload.detail
      : i18n.t("Request failed ({{status}})", { status: response.status })
  }

  protected async readResponse<T>(response: Response): Promise<T> {
    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  }
}

export const apiClient: ApiClient = new FetchApiClient()
