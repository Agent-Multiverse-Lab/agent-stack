import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { useTranslation } from "@/i18n"
import { Link } from "react-router"

type NavItem = {
  title: string
  url: string
  icon?: React.ReactNode
  isActive?: boolean
}

export function NavMain({ items }: { items: NavItem[] }) {
  const { t } = useTranslation()

  return (
    <SidebarGroup className="pt-3 pb-0">
      <nav aria-label={t("Primary navigation")}>
        <SidebarMenu className="gap-0.5">
          {items.map((item) => (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton
                render={
                  <Link to={item.url} />
                }
                isActive={item.isActive}
                className={item.title === "New chat" ? "mb-2 border border-input bg-card text-primary shadow-[0_3px_4px_rgb(0_10_20/0.02)] data-active:bg-card" : undefined}
                tooltip={t(item.title)}
                aria-current={item.isActive ? "page" : undefined}
              >
                {item.icon}
                <span>{t(item.title)}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </nav>
    </SidebarGroup>
  )
}
