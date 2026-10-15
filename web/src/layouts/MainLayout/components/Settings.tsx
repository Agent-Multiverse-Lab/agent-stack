import { type CSSProperties, type ReactNode, useEffect, useState } from "react";
import { useTheme } from "next-themes";
import type { LucideIcon } from "lucide-react";
import {
  BotIcon,
  DatabaseIcon,
  InfoIcon,
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
  Field,
  FieldContent,
  FieldGroup,
  FieldSeparator,
  FieldTitle,
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
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from "@/components/ui/sidebar";
import { Switch } from "@/components/ui/switch";
import type { UserResponse } from "@/types/auth";
import { useTranslation } from "@/i18n";
import SettingsModels from "@/layouts/MainLayout/components/SettingsModels";

type Section = "general" | "account" | "models" | "data" | "about";

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
  const [followUps, setFollowUps] = useState(true);
  const [improveModel, setImproveModel] = useState(false);

  useEffect(() => {
    if (open) setSection("general");
  }, [open]);

  const sections: SectionOption[] = [
    { id: "general", name: t("General"), icon: Settings2Icon },
    { id: "account", name: t("Account"), icon: UserRoundIcon },
    { id: "models", name: t("Models"), icon: BotIcon },
    { id: "data", name: t("Data Controls"), icon: DatabaseIcon },
    { id: "about", name: t("About"), icon: InfoIcon },
  ];
  const currentSection =
    sections.find((item) => item.id === section) ?? sections[0];

  const setting = (label: string, control: ReactNode) => (
    <Field orientation="horizontal" className="min-h-14 py-3">
      <FieldContent>
        <FieldTitle>{label}</FieldTitle>
      </FieldContent>
      {control}
    </Field>
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
        className="z-[101] top-[5vh] h-[min(84dvh,840px)] w-[90%] max-w-[980px] translate-y-0 [&>[data-slot=dialog-close]]:top-2.5 [&>[data-slot=dialog-close]]:right-auto [&>[data-slot=dialog-close]]:left-3.5 [&>[data-slot=dialog-close]]:size-8 overflow-hidden p-0"
      >
        <DialogTitle className="sr-only">{t("Settings")}</DialogTitle>
        <DialogDescription className="sr-only">
          {t("Application settings.")}
        </DialogDescription>

        <SidebarProvider
          className="min-h-0 items-start"
          style={{ "--sidebar-width": "11rem" } as CSSProperties}
        >
          <Sidebar
            collapsible="none"
            aria-label={t("Settings sections")}
            className="border-r border-border bg-secondary"
          >
            <SidebarContent>
              <SidebarGroup className="px-2.5 pt-[52px] pb-3">
                <SidebarGroupContent>
                  <SidebarMenu className="gap-2">
                    {sections.map((item) => {
                      const Icon = item.icon;
                      return (
                        <SidebarMenuItem key={item.id}>
                          <SidebarMenuButton
                            type="button"
                            size="default"
                            className="h-9 gap-2.5 px-3 py-1.5 text-[15px] [&>svg]:size-[18px]"
                            isActive={section === item.id}
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

          <main className="flex h-full min-w-0 flex-1 flex-col overflow-hidden">
            <ScrollArea className="min-h-0 flex-1">
              <section
                className="p-4"
                aria-live="polite"
                aria-labelledby="settings-section-title"
              >
                <h2
                  id="settings-section-title"
                  className="my-3 text-[16px] leading-[1.4] font-medium"
                >
                  {currentSection.name}
                </h2>

                {section === "models" ? (
                  <SettingsModels />
                ) : section === "general" ? (
                  <FieldGroup className="max-w-3xl gap-0">
                    {setting(
                      t("Theme"),
                      <Select
                        value={theme}
                        onValueChange={(value) => setTheme(value ?? "light")}
                      >
                        <SelectTrigger aria-label={t("Theme")}>
                          <SelectValue />
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
                        <SelectTrigger aria-label={t("Language")}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="en">English</SelectItem>
                          <SelectItem value="zh-CN">简体中文</SelectItem>
                        </SelectContent>
                      </Select>,
                    )}
                    <FieldSeparator />
                    {setting(
                      t("Show follow-up suggestions"),
                      <Switch
                        aria-label={t("Show follow-up suggestions")}
                        checked={followUps}
                        onCheckedChange={setFollowUps}
                      />,
                    )}
                  </FieldGroup>
                ) : section === "account" ? (
                  <FieldGroup className="max-w-3xl gap-0">
                    {setting(
                      t("Status"),
                      <Badge variant="outline">
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
                      <Badge variant="outline">{user?.email ?? "—"}</Badge>,
                    )}
                  </FieldGroup>
                ) : section === "data" ? (
                  <FieldGroup className="max-w-3xl gap-0">
                    {setting(
                      t("Improve the model"),
                      <Switch
                        aria-label={t("Improve the model")}
                        checked={improveModel}
                        onCheckedChange={setImproveModel}
                      />,
                    )}
                  </FieldGroup>
                ) : (
                  <FieldGroup className="max-w-3xl gap-0">
                    {setting(
                      t("Product"),
                      <Badge variant="outline">AM</Badge>,
                    )}
                    <FieldSeparator />
                    {setting(
                      t("Version"),
                      <Badge variant="secondary">{t("Preview")}</Badge>,
                    )}
                  </FieldGroup>
                )}
              </section>
            </ScrollArea>
          </main>
        </SidebarProvider>
      </DialogContent>
    </Dialog>
  );
}
