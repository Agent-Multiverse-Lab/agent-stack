import type { LibraryItem } from "@/types/library"

export const INITIAL_MOCK_ITEMS: LibraryItem[] = [
  {
    id: "folder-1",
    name: "Design Assets & Icons",
    type: "folder",
    source: "uploaded",
    sizeBytes: 0,
    itemCount: 14,
    updatedAt: "2026-08-11 14:30",
    createdAt: "2026-08-10 09:15"
  },
  {
    id: "img-1",
    name: "Hero_Banner_v2.png",
    type: "image",
    source: "generated",
    sizeBytes: 3450000,
    mimeType: "image/png",
    thumbnailUrl: "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=400&q=80",
    updatedAt: "2026-08-11 11:20",
    createdAt: "2026-08-11 11:20"
  },
  {
    id: "doc-1",
    name: "Product_Architecture_Spec.pdf",
    type: "document",
    source: "uploaded",
    sizeBytes: 2180000,
    mimeType: "application/pdf",
    updatedAt: "2026-08-10 18:45",
    createdAt: "2026-08-10 18:45"
  },
  {
    id: "sheet-1",
    name: "Q3_Financial_Projection.xlsx",
    type: "spreadsheet",
    source: "uploaded",
    sizeBytes: 1540000,
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    updatedAt: "2026-08-09 16:10",
    createdAt: "2026-08-09 16:10"
  },
  {
    id: "ppt-1",
    name: "AI_MultiAgent_Pitch_Deck.pptx",
    type: "presentation",
    source: "generated",
    sizeBytes: 8900000,
    mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    updatedAt: "2026-08-08 20:00",
    createdAt: "2026-08-08 20:00"
  },
  {
    id: "note-1",
    name: "User Feedback & Action Items",
    type: "note",
    source: "uploaded",
    sizeBytes: 1240,
    noteContent: "Key action items: 1. Refine library toolbar layout. 2. Implement lazy loading for file list.",
    updatedAt: "2026-08-11 09:05",
    createdAt: "2026-08-11 09:05"
  },
  {
    id: "img-2",
    name: "Dashboard_Mockup_Dark.jpg",
    type: "image",
    source: "uploaded",
    sizeBytes: 1850000,
    mimeType: "image/jpeg",
    thumbnailUrl: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=400&q=80",
    updatedAt: "2026-08-07 15:40",
    createdAt: "2026-08-07 15:40"
  },
  {
    id: "doc-2",
    name: "API_Integration_Guide.md",
    type: "document",
    source: "generated",
    sizeBytes: 42000,
    mimeType: "text/markdown",
    updatedAt: "2026-08-06 13:12",
    createdAt: "2026-08-06 13:12"
  },
  {
    id: "folder-2",
    name: "Marketing Campaigns 2026",
    type: "folder",
    source: "uploaded",
    sizeBytes: 0,
    itemCount: 8,
    updatedAt: "2026-08-05 10:00",
    createdAt: "2026-08-01 12:00"
  },
  {
    id: "img-3",
    name: "Brand_Logo_Variants.svg",
    type: "image",
    source: "generated",
    sizeBytes: 520000,
    mimeType: "image/svg+xml",
    thumbnailUrl: "https://images.unsplash.com/photo-1626785774573-4b799315345d?auto=format&fit=crop&w=400&q=80",
    updatedAt: "2026-08-04 17:30",
    createdAt: "2026-08-04 17:30"
  },
  {
    id: "sheet-2",
    name: "User_Analytics_Export.csv",
    type: "spreadsheet",
    source: "generated",
    sizeBytes: 860000,
    mimeType: "text/csv",
    updatedAt: "2026-08-03 14:22",
    createdAt: "2026-08-03 14:22"
  },
  {
    id: "ppt-2",
    name: "Sprint_Review_August.pptx",
    type: "presentation",
    source: "uploaded",
    sizeBytes: 6400000,
    mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    updatedAt: "2026-08-02 19:10",
    createdAt: "2026-08-02 19:10"
  },
  {
    id: "note-2",
    name: "Meeting Notes - Knowledge Base Pipeline",
    type: "note",
    source: "uploaded",
    sizeBytes: 2300,
    noteContent: "Discussed document parsing flow and Milvus vector index lifecycle.",
    updatedAt: "2026-08-01 11:45",
    createdAt: "2026-08-01 11:45"
  },
  {
    id: "img-4",
    name: "Workflow_Diagram_v1.png",
    type: "image",
    source: "generated",
    sizeBytes: 2100000,
    mimeType: "image/png",
    thumbnailUrl: "https://images.unsplash.com/photo-1542744094-3a3172720449?auto=format&fit=crop&w=400&q=80",
    updatedAt: "2026-07-30 08:30",
    createdAt: "2026-07-30 08:30"
  },
  {
    id: "doc-3",
    name: "Security_Audit_Report.pdf",
    type: "document",
    source: "uploaded",
    sizeBytes: 4300000,
    mimeType: "application/pdf",
    updatedAt: "2026-07-28 16:50",
    createdAt: "2026-07-28 16:50"
  }
]

export function generateMoreMockItems(batchIndex: number): LibraryItem[] {
  const types: Array<LibraryItem["type"]> = ["image", "document", "spreadsheet", "presentation", "note"]
  const sources: Array<LibraryItem["source"]> = ["uploaded", "generated"]
  
  return Array.from({ length: 6 }).map((_, idx) => {
    const itemNumber = batchIndex * 6 + idx + 1
    const itemType = types[idx % types.length]
    const itemSource = sources[(idx + batchIndex) % sources.length]
    
    return {
      id: `lazy-item-${batchIndex}-${idx}`,
      name: `Archived_Resource_${itemNumber}.${itemType === "image" ? "png" : itemType === "document" ? "docx" : itemType === "spreadsheet" ? "xlsx" : itemType === "presentation" ? "pptx" : "txt"}`,
      type: itemType,
      source: itemSource,
      sizeBytes: Math.floor(Math.random() * 5000000) + 100000,
      mimeType: itemType === "image" ? "image/png" : "application/octet-stream",
      thumbnailUrl: itemType === "image" ? "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=400&q=80" : undefined,
      updatedAt: `2026-07-${Math.max(1, 28 - batchIndex)} 10:00`,
      createdAt: `2026-07-${Math.max(1, 28 - batchIndex)} 10:00`
    }
  })
}
