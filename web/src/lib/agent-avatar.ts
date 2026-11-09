import { Avatar, Style } from "@dicebear/core"
import lorelei from "@dicebear/styles/lorelei.json" with { type: "json" }

const agentStyle = new Style(lorelei)
const avatarCache = new Map<string, string>()
const backgroundColors = ["dce5f3", "f5ddd6", "f4ebc9", "dcebe3"]

export function getAgentAvatarUrl(seed: string): string {
  const normalizedSeed = seed.trim() || "agent"
  const cached = avatarCache.get(normalizedSeed)
  if (cached) return cached

  const url = new Avatar(agentStyle, {
    seed: `agent:${normalizedSeed}`,
    size: 256,
    backgroundColor: [...backgroundColors],
  }).toDataUri()
  avatarCache.set(normalizedSeed, url)
  return url
}
