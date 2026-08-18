export type LibraryItemType =
  | "image"
  | "document"
  | "spreadsheet"
  | "presentation"
  | "folder"
  | "note"

export type LibraryItemSource = "uploaded" | "generated"

export type LibraryCategory = "all" | "images" | "documents"

export type LibraryViewMode = "grid" | "list"

export interface LibraryItem {
  id: string
  name: string
  type: LibraryItemType
  source: LibraryItemSource
  sizeBytes: number
  updatedAt: string
  createdAt: string
  mimeType?: string
  thumbnailUrl?: string
  description?: string
  noteContent?: string
  itemCount?: number // Applicable for folders
}

export interface LibraryFilterState {
  category: LibraryCategory
  fileType: LibraryItemType | "all"
  source: LibraryItemSource | "all"
  searchQuery: string
}

export interface CreateFolderPayload {
  name: string
}

export interface CreateNotePayload {
  title: string
  content: string
}
