import { useTheme } from "next-themes"
import { Toaster as Sonner, type ToasterProps } from "sonner"
import { CircleCheckIcon, InfoIcon, TriangleAlertIcon, OctagonXIcon, Loader2Icon } from "lucide-react"

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      icons={{
        success: (
          <CircleCheckIcon className="size-4 text-success" />
        ),
        info: (
          <InfoIcon className="size-4 text-primary" />
        ),
        warning: (
          <TriangleAlertIcon className="size-4 text-warning" />
        ),
        error: (
          <OctagonXIcon className="size-4 text-destructive" />
        ),
        loading: (
          <Loader2Icon className="size-4 animate-spin" />
        ),
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--success-bg": "color-mix(in srgb, var(--success) 10%, var(--popover))",
          "--success-border": "color-mix(in srgb, var(--success) 25%, var(--popover))",
          "--success-text": "var(--success)",
          "--warning-bg": "color-mix(in srgb, var(--warning) 10%, var(--popover))",
          "--warning-border": "color-mix(in srgb, var(--warning) 25%, var(--popover))",
          "--warning-text": "var(--warning)",
          "--error-bg": "color-mix(in srgb, var(--destructive) 10%, var(--popover))",
          "--error-border": "color-mix(in srgb, var(--destructive) 25%, var(--popover))",
          "--error-text": "var(--destructive)",
          "--info-bg": "var(--selection)",
          "--info-border": "color-mix(in srgb, var(--primary) 25%, var(--popover))",
          "--info-text": "var(--selection-foreground)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast: "cn-toast",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
