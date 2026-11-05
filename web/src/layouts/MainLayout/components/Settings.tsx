import { type CSSProperties, type ReactNode, useEffect, useState } from "react";
import { useTheme } from "next-themes";
import type { LucideIcon } from "lucide-react";
import {
  BotIcon,
  BlocksIcon,
  PlugIcon,
  Settings2Icon,
  UserRoundIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  FieldGroup,
  FieldSeparator,
} from "@/components/ui/field";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from "@/components/ui/sidebar";
import type { UserResponse } from "@/api/auth";
import { useTranslation } from "@/i18n";
import SettingsModels from "@/layouts/MainLayout/components/SettingsModels";
import { Skill } from "./settings-extensions/Skill";
import { Mcp } from "./settings-extensions/Mcp";

type Section = "general" | "account" | "models" | "skills" | "mcp";

type SectionOption = {
  id: Section;
  icon: LucideIcon;
  name: string;
};

type SettingsProps = {
  open: boolean;
  close: () => void;
  user: UserResponse | null;
};

export function Settings({ open, close, user }: SettingsProps) {
  const { t, i18n } = useTranslation();
  const [section, setSection] = useState<Section>("general");
  const { theme = "light", setTheme } = useTheme();

  useEffect(() => {
    if (open) setSection("general");
  }, [open]);

  const sections: SectionOption[] = [
    { id: "general", name: t("General"), icon: Settings2Icon },
    { id: "account", name: t("Account"), icon: UserRoundIcon },
    { id: "models", name: t("Models"), icon: BotIcon },
    { id: "skills", name: t("Skills"), icon: BlocksIcon },
    { id: "mcp", name: "MCP", icon: PlugIcon },
  ];
  const currentSection =
    sections.find((item) => item.id === section) ?? sections[0];

  const setting = (label: string, control: ReactNode) => (
    <div className="flex min-h-10 items-center gap-6 py-2">
      <span className="w-28 shrink-0 text-[13px] font-medium text-foreground">
        {label}
      </span>
      <div className="flex items-center">
        {control}
      </div>
    </div>
  );

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) close();
      }}
    >
      <DialogContent
        overlayClassName="z-[100]"
        className="z-[101] h-[520px] max-h-[85dvh] w-[840px] max-w-[92vw] overflow-hidden p-0 [&>[data-slot=dialog-close]]:top-3 [&>[data-slot=dialog-close]]:right-4 [&>[data-slot=dialog-close]]:size-7 [&_svg]:size-4"
      >
        <DialogDescription className="sr-only">
          {t("Application settings.")}
        </DialogDescription>

        <SidebarProvider
          className="h-full min-h-0 w-full items-stretch"
          style={{ "--sidebar-width": "11rem" } as CSSProperties}
        >
          <Sidebar
            collapsible="none"
            aria-label={t("Settings sections")}
            className="w-(--sidebar-width) shrink-0 border-r border-border bg-sidebar"
          >
            <SidebarHeader className="flex h-13 shrink-0 items-center border-b border-border px-4 pt-3 pb-2">
              <DialogTitle className="text-sm font-semibold text-sidebar-foreground">
                {t("Settings")}
              </DialogTitle>
            </SidebarHeader>

            <SidebarContent className="p-2">
              <SidebarGroup className="p-0">
                <SidebarGroupContent>
                  <SidebarMenu className="gap-0.5">
                    {sections.map((item) => {
                      const Icon = item.icon;
                      return (
                        <SidebarMenuItem key={item.id}>
                          <SidebarMenuButton
                            type="button"
                            size="default"
                            className="h-8 gap-2.5 px-2.5 py-1 text-[13px] font-medium [&>svg]:size-4"
                            isActive={section === item.id}
                            aria-current={section === item.id ? "page" : undefined}
                            onClick={() => setSection(item.id)}
                          >
                            <Icon aria-hidden="true" />
                            <span>{item.name}</span>
                          </SidebarMenuButton>
                        </SidebarMenuItem>
                      );
                    })}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            </SidebarContent>
          </Sidebar>

          <main className="flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-background">
            <div className="flex h-13 shrink-0 items-center px-5 pr-12 pt-3 pb-2">
              <h2
                id="settings-section-title"
                className="text-sm font-semibold text-foreground"
              >
                {currentSection.name}
              </h2>
            </div>

            <div className="min-h-0 flex-1 px-5 pb-5">
              <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-secondary/40 shadow-2xs">
                <ScrollArea className="h-full">
                  <section
                    className="p-4.5"
                    aria-live="polite"
                    aria-labelledby="settings-section-title"
                  >
                    {section === "models" ? (
                      <SettingsModels />
                    ) : section === "skills" ? (
                      <Skill key={user?.uid ?? "guest"} />
                    ) : section === "mcp" ? (
                      <Mcp key={user?.uid ?? "guest"} />
                    ) : section === "general" ? (
                      <FieldGroup className="max-w-2xl gap-0">
                        {setting(
                          t("Theme"),
                          <Select
                            value={theme}
                            onValueChange={(value) => setTheme(value ?? "light")}
                          >
                            <SelectTrigger aria-label={t("Theme")} className="h-8 w-[140px] px-2.5 text-xs">
                              <SelectValue>
                                {t(theme === "dark" ? "Dark" : theme === "system" ? "System" : "Light")}
                              </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="light">{t("Light")}</SelectItem>
                              <SelectItem value="system">{t("System")}</SelectItem>
                              <SelectItem value="dark">{t("Dark")}</SelectItem>
                            </SelectContent>
                          </Select>,
                        )}
                        <FieldSeparator />
                        {setting(
                          t("Language"),
                          <Select
                            value={
                              i18n.resolvedLanguage === "zh-CN" ? "zh-CN" : "en"
                            }
                            onValueChange={(value) => {
                              if (value) void i18n.changeLanguage(value);
                            }}
                          >
                            <SelectTrigger aria-label={t("Language")} className="h-8 w-[140px] px-2.5 text-xs">
                              <SelectValue>
                                {i18n.resolvedLanguage === "zh-CN" ? "简体中文" : "English"}
                              </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="en">English</SelectItem>
                              <SelectItem value="zh-CN">简体中文</SelectItem>
                            </SelectContent>
                          </Select>,
                        )}
                      </FieldGroup>
                    ) : (
                      <FieldGroup className="max-w-2xl gap-0">
                        {setting(
                          t("Status"),
                          <Badge variant="outline" className="text-xs font-normal px-2.5 py-0.5">
                            {user
                              ? user.is_active
                                ? t("Active")
                                : t("Inactive")
                              : t("Not logged in")}
                          </Badge>,
                        )}
                        <FieldSeparator />
                        {setting(
                          t("Account"),
                          <Badge variant="outline" className="text-xs font-normal px-2.5 py-0.5">{user?.email ?? "—"}</Badge>,
                        )}
                      </FieldGroup>
                    )}
                  </section>
                </ScrollArea>
              </div>
            </div>
          </main>
        </SidebarProvider>
      </DialogContent>
    </Dialog>
  );
}
