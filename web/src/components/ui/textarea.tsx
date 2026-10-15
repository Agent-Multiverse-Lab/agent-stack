import * as React from "react"
import { cn } from "cn"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-lg border border-input bg-card px-[11px] py-1 text-sm transition-colors duration-(--hover-transition-duration) outline-none hover:border-primary-hover focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/15 placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
