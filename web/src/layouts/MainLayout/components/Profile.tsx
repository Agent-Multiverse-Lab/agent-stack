import { X } from "lucide-react";
import type { UserResponse } from "@/api/auth";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useTranslation } from "@/i18n";

export function Profile({
  open,
  close,
  user,
}: {
  open: boolean;
  close: () => void;
  user: UserResponse | null;
}) {
  const { t } = useTranslation();
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) close();
      }}
    >
      <DialogContent
        showCloseButton={false}
        overlayClassName="z-[100]"
        className="z-[101] w-[440px] max-w-[440px] gap-0 overflow-hidden rounded-lg bg-popover p-0 text-foreground"
      >
        <DialogHeader className="flex min-h-[3.25rem] flex-row items-center justify-between px-5">
          <DialogTitle id="profile-title" className="text-[0.95rem] font-semibold">
            {t("Profile")}
          </DialogTitle>
          <DialogClose
            render={<Button variant="ghost" size="icon-sm" />}
            aria-label={t("Close profile")}
          >
            <X size={19} />
          </DialogClose>
        </DialogHeader>
        <DialogDescription className="sr-only">
          {t("Your account details.")}
        </DialogDescription>
        <div className="grid gap-6 px-5 pt-3 pb-6">
          <div className="grid justify-items-center gap-3 border-b border-border pb-6 text-center">
            <Avatar className="size-14" aria-hidden="true">
              <AvatarFallback className="bg-muted font-mono text-lg font-bold text-muted-foreground">
                A
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="font-semibold">{t("AM User")}</p>
              <p className="text-sm text-muted-foreground">
                {user?.email ?? t("Loading account…")}
              </p>
            </div>
          </div>
          <dl className="grid text-sm">
            <div className="flex justify-between border-b border-border py-3">
              <dt>{t("Email")}</dt>
              <dd className="text-muted-foreground">{user?.email ?? "—"}</dd>
            </div>
            <div className="flex justify-between py-3">
              <dt>{t("Status")}</dt>
              <dd className="text-muted-foreground">
                {user ? (user.is_active ? t("Active") : t("Inactive")) : t("Loading")}
              </dd>
            </div>
          </dl>
        </div>
      </DialogContent>
    </Dialog>
  );
}
