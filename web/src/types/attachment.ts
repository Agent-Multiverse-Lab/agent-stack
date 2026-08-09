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

export type ChatAttachment =
  | UploadedAttachmentResponse
  | ThreadMessageAttachmentResponse
