import { type CSSProperties, type ReactNode, useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  BotIcon,
  DatabaseIcon,
  InfoIcon,
  Settings2Icon,
  UserRoundIcon,
} from "lucide-react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
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
import { Separator } from "@/components/ui/separator";
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
  const [theme, setTheme] = useState("light");
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
    <Field orientation="responsive" className="min-h-16 py-4">
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
        overlayClassName="z-[100] bg-primary/36"
        className="z-[101] h-[min(92dvh,760px)] overflow-hidden p-0 sm:max-w-[calc(100%-2rem)] md:max-w-[760px] lg:max-w-[1120px]"
      >
        <DialogTitle className="sr-only">{t("Settings")}</DialogTitle>
        <DialogDescription className="sr-only">
          {t("Application settings.")}
        </DialogDescription>

        <SidebarProvider
          className="min-h-0 items-start"
          style={{ "--sidebar-width": "13rem" } as CSSProperties}
        >
          <Sidebar
            collapsible="none"
            aria-label={t("Settings sections")}
            className="hidden md:flex"
          >
            <SidebarContent>
              <SidebarGroup className="py-4">
                <SidebarGroupContent>
                  <SidebarMenu>
                    {sections.map((item) => {
                      const Icon = item.icon;
                      return (
                        <SidebarMenuItem key={item.id}>
                          <SidebarMenuButton
                            type="button"
                            size="lg"
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

          <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
            <header className="flex h-14 shrink-0 items-center px-4 pr-12 md:px-6 md:pr-12">
              <Breadcrumb className="hidden md:block">
                <BreadcrumbList>
                  <BreadcrumbItem>
                    <span className="text-muted-foreground">
                      {t("Settings")}
                    </span>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <BreadcrumbPage>{currentSection.name}</BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>

              <Select
                value={section}
                onValueChange={(value) => {
                  if (value) setSection(value as Section);
                }}
              >
                <SelectTrigger
                  aria-label={t("Settings sections")}
                  className="h-10 w-full md:hidden"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent align="start">
                  {sections.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </header>
            <Separator />

            <ScrollArea className="min-h-0 flex-1">
              <section
                className="px-4 pt-5 pb-6 md:px-6"
                aria-live="polite"
                aria-labelledby="settings-section-title"
              >
                <h2
                  id="settings-section-title"
                  className="mb-5 text-lg font-semibold"
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
