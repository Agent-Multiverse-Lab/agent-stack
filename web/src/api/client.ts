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
  /**
   * 发起底层 HTTP 请求，自动处理鉴权头与非 2xx 错误响应。
   * @param path 请求路径。
   * @param options 请求配置与鉴权标记。
   * @returns 原始 Fetch Response 对象。
   */
  apiFetch(
    path: string,
    options: ApiFetchOptions
  ): Promise<Response>

  /**
   * 发起 GET 请求并解析 JSON 响应。
   * @param path 请求路径。
   * @param options 请求配置与鉴权标记。
   * @returns 解析后的响应数据。
   */
  apiGet<T>(
    path: string,
    options: ApiRequestOptions
  ): Promise<T>

  /**
   * 发起 POST 请求并解析 JSON 响应（支持 JSON 或 FormData 请求体）。
   * @param path 请求路径。
   * @param body 请求体，未传时发送空请求体。
   * @param options 请求配置与鉴权标记。
   * @returns 解析后的响应数据。
   */
  apiPost<TResponse, TBody = undefined>(
    path: string,
    body: TBody,
    options: ApiRequestOptions
  ): Promise<TResponse>

  /**
   * 发起 DELETE 请求并解析响应。
   * @param path 请求路径。
   * @param options 请求配置与鉴权标记。
   * @returns 解析后的响应数据（204 时返回 undefined）。
   */
  apiDelete<T = void>(
    path: string,
    options: ApiRequestOptions
  ): Promise<T>
}

export class FetchApiClient implements ApiClient {
  /**
   * 发起底层 HTTP 请求；当 requiresAuth 为 true 时附加 Bearer Token。
   * @param path 请求路径。
   * @param options 请求配置与鉴权标记。
   * @returns 原始 Fetch Response 对象。
   */
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

  /**
   * 发起 GET 请求并读取响应体。
   * @param path 请求路径。
   * @param options 请求配置与鉴权标记。
   * @returns 解析后的响应数据。
   */
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

  /**
   * 发起 POST 请求并读取响应体；FormData 保持原样，其余对象序列化为 JSON。
   * @param path 请求路径。
   * @param body 请求体。
   * @param options 请求配置与鉴权标记。
   * @returns 解析后的响应数据。
   */
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

  /**
   * 发起 DELETE 请求并读取响应体。
   * @param path 请求路径。
   * @param options 请求配置与鉴权标记。
   * @returns 解析后的响应数据。
   */
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

  /**
   * 从失败响应中提取错误详情文本。
   * @param response 失败的 Fetch Response 对象。
   * @returns 可展示的错误提示字符串。
   */
  protected async readApiError(response: Response) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: unknown
    } | null
    return typeof payload?.detail === "string"
      ? payload.detail
      : i18n.t("Request failed ({{status}})", { status: response.status })
  }

  /**
   * 解析成功响应为 JSON；204 No Content 返回 undefined。
   * @param response 成功的 Fetch Response 对象。
   * @returns 解析后的泛型结果。
   */
  protected async readResponse<T>(response: Response): Promise<T> {
    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  }
}

export const apiClient: ApiClient = new FetchApiClient()
