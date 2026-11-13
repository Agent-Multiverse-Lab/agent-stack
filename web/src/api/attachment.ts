import { apiClient } from "@/api/client"

export interface UploadedAttachmentResponse {
  file_id: string
  file_name: string
  content_type: string
  file_size: number
  bucket_name: string
  object_name: string
  access_url: string
}

export interface ThreadMessageAttachmentResponse {
  file_id: string
  file_name: string
  content_type: string
  file_size: number
  available: boolean
  access_url: string | null
}

/**
 * 批量上传对话附件文件。
 * @param files 待上传的本地文件列表。
 * @returns 上传成功的附件元数据及访问地址列表。
 */
export const uploadChatAttachments = (files: File[]) => {
  const body = new FormData()
  files.forEach((file) => body.append("files", file, file.name))
  return apiClient.apiPost<UploadedAttachmentResponse[], FormData>(
    "/api/chat/attachment/upload",
    body,
    { requiresAuth: true }
  )
}
