export type MentionType = "file" | "knowledge" | "mcp" | "skill" | "agent";

export interface MentionItem {
  type: MentionType;
  value: string;
  label: string;
  description?: string;
  isDir?: boolean;
}

export interface MentionSources {
  files?: MentionItem[];
  knowledgeBases?: MentionItem[];
  agents?: MentionItem[];
}

export type MentionSegment =
  | {
      kind: "text";
      text: string;
      start: number;
      end: number;
    }
  | {
      kind: "mention";
      raw: string;
      type: MentionType;
      value: string;
      start: number;
      end: number;
    };

const MENTION_TYPES: MentionType[] = [
  "file",
  "knowledge",
  "mcp",
  "skill",
  "agent",
];

const mentionTokenRegex = new RegExp(
  `@(${MENTION_TYPES.join("|")}):(?:"((?:\\\\.|[^"\\\\])*)"|(\\S+))`,
  "g",
);

const unquoteMentionValue = (value: string) =>
  value.replace(/\\(["\\])/g, "$1");

export function formatMentionToken(type: MentionType, value: string): string {
  const rawValue = String(value ?? "");
  if (/\s|["\\]/.test(rawValue)) {
    return `@${type}:"${rawValue.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
  }
  return `@${type}:${rawValue}`;
}

export function parseMentionText(text = ""): MentionSegment[] {
  const value = String(text || "");
  const segments: MentionSegment[] = [];
  let lastIndex = 0;

  mentionTokenRegex.lastIndex = 0;
  for (const match of value.matchAll(mentionTokenRegex)) {
    const raw = match[0];
    const start = match.index ?? 0;
    const end = start + raw.length;

    if (start > lastIndex) {
      segments.push({
        kind: "text",
        text: value.slice(lastIndex, start),
        start: lastIndex,
        end: start,
      });
    }

    const type = match[1] as MentionType;
    const quotedValue = match[2];
    const rawValue = match[3] ?? "";
    segments.push({
      kind: "mention",
      raw,
      type,
      value:
        quotedValue !== undefined ? unquoteMentionValue(quotedValue) : rawValue,
      start,
      end,
    });

    lastIndex = end;
  }

  if (lastIndex < value.length) {
    segments.push({
      kind: "text",
      text: value.slice(lastIndex),
      start: lastIndex,
      end: value.length,
    });
  }

  return segments;
}

export function getMentionDisplayLabel(
  type: MentionType,
  value: string,
): string {
  if (type === "file") {
    const normalized = String(value ?? "").replace(/\/+$/, "");
    const parts = normalized.split("/").filter(Boolean);
    return parts.at(-1) || value;
  }
  return String(value ?? "").trim() || type;
}

export function findActiveMentionQuery(
  text = "",
  rawCaretOffset = 0,
): { start: number; end: number; query: string } | null {
  const value = String(text || "");
  const offset = Math.max(0, Math.min(rawCaretOffset, value.length));
  const segments = parseMentionText(value);
  const mentionAtCursor = segments.find(
    (segment) =>
      segment.kind === "mention" &&
      offset > segment.start &&
      offset <= segment.end,
  );
  if (mentionAtCursor) return null;

  const textBeforeCursor = value.slice(0, offset);
  const atIndex = textBeforeCursor.lastIndexOf("@");
  if (atIndex === -1) return null;

  const query = textBeforeCursor.slice(atIndex + 1);
  if (query.includes("@") || query.includes(":") || /\s/.test(query)) {
    return null;
  }

  return { start: atIndex, end: offset, query };
}

export function replaceRawRange(
  text = "",
  start = 0,
  end = start,
  replacement = "",
): string {
  const value = String(text || "");
  const safeStart = Math.max(0, Math.min(start, value.length));
  const safeEnd = Math.max(safeStart, Math.min(end, value.length));
  return value.slice(0, safeStart) + replacement + value.slice(safeEnd);
}

export function expandMentionDeletionRange(
  text = "",
  start = 0,
  end = start,
  direction: "backward" | "forward" = "backward",
): { start: number; end: number } | null {
  const value = String(text || "");
  const safeStart = Math.max(0, Math.min(start, value.length));
  const safeEnd = Math.max(safeStart, Math.min(end, value.length));
  const cursor = safeStart;

  const mentions = parseMentionText(value).filter(
    (segment): segment is Extract<MentionSegment, { kind: "mention" }> =>
      segment.kind === "mention",
  );

  if (safeStart !== safeEnd) {
    const touchedMentions = mentions.filter(
      (segment) => segment.start < safeEnd && segment.end > safeStart,
    );
    if (!touchedMentions.length) return null;

    return {
      start: Math.min(safeStart, ...touchedMentions.map((s) => s.start)),
      end: Math.max(safeEnd, ...touchedMentions.map((s) => s.end)),
    };
  }

  if (direction === "forward") {
    const mention = mentions.find(
      (segment) => cursor >= segment.start && cursor < segment.end,
    );
    if (!mention) return null;
    const includeTrailingSpace = value[mention.end] === " ";
    return {
      start: mention.start,
      end: includeTrailingSpace ? mention.end + 1 : mention.end,
    };
  }

  const mention = mentions.find(
    (segment) => cursor > segment.start && cursor <= segment.end,
  );
  if (mention) {
    return { start: mention.start, end: mention.end };
  }

  return null;
}

export function splitTextByQuery(
  text: string,
  query: string,
): Array<{ text: string; isMatch: boolean }> {
  if (!text) return [];
  if (!query) return [{ text, isMatch: false }];

  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp(`(${escaped})`, "gi");
  return text
    .split(regex)
    .filter((part) => part.length > 0)
    .map((part) => ({
      text: part,
      isMatch: part.toLowerCase() === query.toLowerCase(),
    }));
}
