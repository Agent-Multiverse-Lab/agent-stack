/** Illustrative, in-memory records only. These are never server configuration. */
export type ExtensionKind = "skills" | "mcp";
export type SkillScope = "all" | "research";
export type McpTransport = "http" | "sse";
export type McpAuthentication = "none" | "bearer";

interface PreviewBase {
  id: string;
  name: string;
  description: string;
  isEnabled: boolean;
}

export interface SkillPreview extends PreviewBase {
  kind: "skills";
  scope: SkillScope;
  capabilities: string[];
  fileContent: string;
}

export type ToolSchema = boolean | { [key: string]: unknown };

/** Metadata declared by the local fixture, not discovered from an MCP server. */
export interface McpToolPreview {
  name: string;
  description?: string;
  inputSchema?: ToolSchema;
  outputSchema?: ToolSchema;
}

export interface McpPreview extends PreviewBase {
  kind: "mcp";
  transport: McpTransport;
  endpoint: string;
  authentication: McpAuthentication;
  tools: McpToolPreview[];
}

export type ExtensionPreview = SkillPreview | McpPreview;

function createEnglishPreviewItems(kind: ExtensionKind): ExtensionPreview[] {
  if (kind === "skills") {
    return [
      {
        kind, id: "research-brief", name: "Research brief", isEnabled: true,
        description: "Organize source material into a research summary with traceable references.",
        scope: "all", capabilities: ["Read documents", "Structured summaries", "Source references"],
        fileContent: "# Research brief\n\nExample skill file for this local preview.\n\n1. Read the supplied research material.\n2. Summarize its main findings.\n3. Keep references alongside each claim.\n\nThis sample is not installed or executed.",
      },
      {
        kind, id: "spatial-analysis", name: "Spatial analysis", isEnabled: true,
        description: "Explore geographic data and summarize spatial relationships.",
        scope: "research", capabilities: ["Geographic data", "Spatial summaries"],
        fileContent: "# Spatial analysis\n\nExample skill file for this local preview.\n\nInspect supplied geographic data and describe spatial relationships.\n\nThis sample is not installed or executed.",
      },
      {
        kind, id: "writing-review", name: "Writing review", isEnabled: false,
        description: "Review a draft for clarity, structure, and consistent wording.",
        scope: "all", capabilities: ["Review writing", "Clear structure"],
        fileContent: "# Writing review\n\nExample skill file for this local preview.\n\nReview the supplied draft and suggest clear, consistent wording.\n\nThis sample is not installed or executed.",
      },
    ];
  }
  return [
    {
      kind, id: "documents", name: "Document service", isEnabled: true,
      description: "An example connection for browsing and searching documents.",
      transport: "http", endpoint: "https://mcp.example.invalid/documents", authentication: "bearer",
      tools: [
        {
          name: "search_documents", description: "Search documents by keyword and optional collection.",
          inputSchema: {
            type: "object", properties: {
              query: { type: "string" },
              filters: { type: "object", properties: { collection_id: { type: "string" } } },
              limit: { type: "integer", minimum: 1, maximum: 50, default: 10 },
            }, required: ["query"],
          },
          outputSchema: {
            type: "object", properties: {
              documents: { type: "array", items: { type: "object", properties: { id: { type: "string" }, title: { type: "string" } }, required: ["id", "title"] } },
            }, required: ["documents"],
          },
        },
        {
          name: "read_document", description: "Read the text of a document by its identifier.",
          inputSchema: { type: "object", properties: { document_id: { type: "string" } }, required: ["document_id"] },
          outputSchema: { type: "object", properties: { title: { type: "string" }, text: { type: "string" } }, required: ["title", "text"] },
        },
        {
          name: "list_collections", description: "List the collections in the document catalog.",
          inputSchema: { type: "object", properties: {}, additionalProperties: false },
        },
      ],
    },
    {
      kind, id: "database", name: "Database service", isEnabled: true,
      description: "An example connection for inspecting a database catalog.",
      transport: "sse", endpoint: "https://mcp.example.invalid/database", authentication: "none",
      tools: [
        {
          name: "list_tables", description: "List table names in a database schema.",
          inputSchema: { type: "object", properties: { schema: { type: "string" } } },
          outputSchema: { type: "object", properties: { tables: { type: "array", items: { type: "string" } } }, required: ["tables"] },
        },
        {
          name: "describe_table", description: "Inspect the columns of a named table.",
          inputSchema: { type: "object", properties: { table: { type: "string" } }, required: ["table"] },
        },
      ],
    },
    {
      kind, id: "web-search", name: "Web search", isEnabled: false,
      description: "An example connection for finding and reading web sources.",
      transport: "http", endpoint: "https://mcp.example.invalid/search", authentication: "none",
      tools: [
        {
          name: "search_web", description: "Find web pages matching a search query.",
          inputSchema: { type: "object", properties: { query: { type: "string" } }, required: ["query"] },
        },
        {
          name: "read_page", description: "Read the text content of a web page.",
          inputSchema: { type: "object", properties: { url: { type: "string", format: "uri" } }, required: ["url"] },
        },
      ],
    },
  ];
}

export function createPreviewItem(kind: ExtensionKind, id: string): ExtensionPreview {
  const base = { id, name: "", description: "", isEnabled: false };
  return kind === "skills"
    ? { ...base, kind, scope: "all", capabilities: [], fileContent: "# Example skill\n\nThis local preview contains no uploaded or installed skill files." }
    : { ...base, kind, transport: "http", endpoint: "", authentication: "none", tools: [] };
}

export function isPreviewDirty(draft: ExtensionPreview, original: ExtensionPreview): boolean {
  return JSON.stringify(draft) !== JSON.stringify(original);
}

export function createPreviewItems(kind: ExtensionKind, translate: (value: string) => string = (value) => value): ExtensionPreview[] {
  return createEnglishPreviewItems(kind).map((item) => ({
    ...item, name: translate(item.name), description: translate(item.description),
  }));
}
