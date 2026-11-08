import { useMemo } from "react"
import type { ComponentProps } from "react"
import { cn } from "cn"

import { getAgentAvatarUrl } from "@/lib/agent-avatar"

type AgentAvatarProps = Omit<ComponentProps<"img">, "src"> & {
  seed: string
}

export function AgentAvatar({ seed, alt = "", className, ...props }: AgentAvatarProps) {
  const src = useMemo(() => getAgentAvatarUrl(seed), [seed])

  return (
    <img
      src={src}
      alt={alt}
      className={cn("size-8 shrink-0 rounded-[7px] object-cover", className)}
      {...props}
    />
  )
}
