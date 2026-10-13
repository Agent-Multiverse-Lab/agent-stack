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
    <SidebarGroup className="py-1">
      <nav aria-label={t("Primary navigation")}>
        <SidebarMenu className="gap-1">
          {items.map((item) => (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton
                render={
                  <Link to={item.url} />
                }
                isActive={item.isActive}
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
