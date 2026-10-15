import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertAction, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Bot, Eye, EyeOff, Plug, RefreshCw, Search } from "lucide-react";
import deepseekLogo from "@/assets/models/deepseek-color.svg";
import qwenLogo from "@/assets/models/qwen-color.svg";
import {
  discoverProviderModels,
  getModelProvider,
  listModelProviders,
  saveModelProvider,
  testProviderConnection,
} from "@/api/model";
import { useAuth } from "@/context/AuthContext";
import { useTranslation } from "@/i18n";
import type {
  ModelProvider,
  ModelProviderId,
  ModelProviderSummary,
  ModelSettingsRequest,
  SettingsModel,
} from "@/types/model";

const providerLogos: Record<string, string> = {
  deepseek: deepseekLogo,
  dashscope: qwenLogo,
  qwen: qwenLogo,
};

function ProviderMark({ providerId }: { providerId: string }) {
  const logo = providerLogos[providerId];
  return logo ? <img src={logo} alt="" /> : <Bot aria-hidden="true" />;
}
interface Draft extends ModelSettingsRequest {
  key: string;
  keyEdited: boolean;
  hasKey: boolean;
  initialized: boolean;
}
const emptyDraft = (): Draft => ({
  base_url: "",
  is_enabled: false,
  models: [],
  key: "",
  keyEdited: false,
  hasKey: false,
  initialized: false,
});
const providerDraft = (value: ModelProvider): Draft => ({
  base_url: value.base_url,
  is_enabled: value.is_enabled,
  models: value.enabled_models.map((model) => ({
    model_id: model.model_id,
    capabilities: model.capabilities ?? [],
  })),
  key: "",
  keyEdited: false,
  hasKey: value.has_api_key,
  initialized: true,
});

export default function SettingsModels() {
  const { t, i18n } = useTranslation();
  const { accessToken } = useAuth();
  const [providers, setProviders] = useState<ModelProviderSummary[]>([]);
  const [selected, setSelected] = useState<ModelProviderId>("");
  const [drafts, setDrafts] = useState<Partial<Record<string, Draft>>>(
    {},
  );
  const draft = drafts[selected] ?? emptyDraft();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [busy, setBusy] = useState<"save" | "discover" | "test" | null>(null);
  const [candidates, setCandidates] = useState<SettingsModel[] | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [revealKey, setRevealKey] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const version = useRef(0);
  const provider = providers.find((item) => item.provider_id === selected);
  const blocked = loading || loadError || busy !== null || !provider;
  const filteredCandidates =
    candidates?.filter((model) =>
      model.model_id.toLowerCase().includes(search.toLowerCase()),
    ) ?? [];
  function edit(patch: Partial<Draft>) {
    if (!selected) return;
    setDrafts((previous) => ({
      ...previous,
      [selected]: { ...(previous[selected] ?? emptyDraft()), ...patch },
    }));
  }
  const load = useCallback(async () => {
    if (!selected) {
      setLoading(false);
      return;
    }
    const current = ++version.current;
    setLoading(true);
    setLoadError(false);
    try {
      const value = await getModelProvider(selected);
      if (current !== version.current) return;
      setDrafts((previous) =>
        previous[selected]?.initialized
          ? previous
          : {
              ...previous,
              [selected]: providerDraft(value),
            },
      );
    } catch (error) {
      if (current === version.current) {
        setLoadError(true);
        toast.error(error instanceof Error ? error.message : i18n.t("Load failed"));
      }
    } finally {
      if (current === version.current) setLoading(false);
    }
  }, [selected, i18n]);
  useEffect(() => {
    let cancelled = false;
    const current = ++version.current;
    setProviders([]);
    setSelected("");
    setDrafts({});
    setCandidates(null);
    setChosen([]);
    setSearch("");
    setRevealKey(false);
    setLoadError(false);
    if (!accessToken) {
      setLoading(false);
      return;
    }
    setLoading(true);
    void listModelProviders()
      .then((items) => {
        if (cancelled || current !== version.current) return;
        setProviders(items);
        setSelected(items[0]?.provider_id ?? "");
        if (!items.length) setLoading(false);
      })
      .catch((error) => {
        if (cancelled || current !== version.current) return;
        setLoadError(true);
        setLoading(false);
        toast.error(
          error instanceof Error ? error.message : i18n.t("Load failed"),
        );
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, i18n, reloadKey]);
  useEffect(() => {
    if (!selected) return;
    void load();
  }, [load, selected]);
  useEffect(() => {
    setRevealKey(false);
  }, [selected]);
  function request(): ModelSettingsRequest {
    return {
      base_url: draft.base_url,
      is_enabled: draft.is_enabled,
      models: draft.models.map((model) => ({
        ...model,
        capabilities: [...model.capabilities],
      })),
      ...(draft.keyEdited ? { api_key: draft.key } : {}),
    };
  }
  async function act(action: "save" | "discover" | "test") {
    if (blocked || !selected) return;
    const current = version.current;
    const body = request();
    setBusy(action);
    try {
      if (action === "save") {
        const result = await saveModelProvider(selected, body);
        if (current !== version.current) return;
        let saved: ModelProvider;
        try {
          saved = await getModelProvider(selected);
        } catch {
          if (current !== version.current) return;
          edit({ key: "", keyEdited: false });
          toast.warning(t("Saved, but reloading the provider failed"));
          return;
        }
        if (current !== version.current) return;
        setDrafts((previous) => ({
          ...previous,
          [selected]: providerDraft(saved),
        }));
        if (result.cache_refreshed) toast.success(t("Saved"));
        else toast.warning(t("Saved, but refreshing the model cache failed"));
      } else if (action === "discover") {
        const result = await discoverProviderModels(selected, body);
        if (current !== version.current) return;
        setCandidates([
          ...new Map(
            [...body.models, ...result].map((model) => [model.model_id, model]),
          ).values(),
        ]);
        setChosen(body.models.map((model) => model.model_id));
        setSearch("");
      } else {
        const result = await testProviderConnection(selected, body);
        if (current !== version.current) return;
        if (result.success)
          toast.success(
            t("Connection succeeded · {{ms}} ms", { ms: Math.round(result.elapsed_ms) }),
          );
        else
          toast.error(
            `${t("Connection failed: {{error}}", { error: result.error ?? "unknown" })}${result.status_code ? ` (${result.status_code})` : ""}`,
          );
      }
    } catch (error) {
      if (current === version.current)
        toast.error(error instanceof Error ? error.message : t("Operation failed"));
    } finally {
      if (current === version.current) setBusy(null);
    }
  }
  return (
    <FieldGroup className="grid min-h-full min-w-0 grid-cols-[176px_minmax(0,1fr)] content-start gap-9">
      <nav aria-label={t("Model providers")} className="min-w-0">
        <ItemGroup className="flex-col gap-1">
          {providers.map((item) => (
            <Item
              key={item.provider_id}
              render={
                <Button
                  type="button"
                  variant="ghost"
                  disabled={busy !== null || candidates !== null}
                />
              }
              variant={selected === item.provider_id ? "muted" : "default"}
              size="sm"
              aria-pressed={selected === item.provider_id}
              className="min-h-11 shrink-0 flex-nowrap justify-start text-left aria-pressed:bg-selection aria-pressed:text-selection-foreground aria-pressed:shadow-[inset_3px_0_0_var(--selection-foreground)] aria-pressed:hover:bg-selection disabled:opacity-60"
              onClick={() => setSelected(item.provider_id)}
            >
              <ItemMedia
                variant={providerLogos[item.provider_id] ? "image" : "icon"}
                className="size-6"
              >
                <ProviderMark providerId={item.provider_id} />
              </ItemMedia>
              <ItemContent>
                <ItemTitle
                  className={
                    selected === item.provider_id
                      ? "font-semibold"
                      : "text-muted-foreground"
                  }
                >
                  {item.name}
                </ItemTitle>
              </ItemContent>
            </Item>
          ))}
        </ItemGroup>
      </nav>

      <FieldGroup
        className="min-h-[490px] min-w-0 gap-0"
        aria-busy={loading}
      >
        <Item className="mb-7 flex-nowrap px-0 py-0">
          <ItemMedia
            variant={provider && providerLogos[provider.provider_id] ? "image" : "icon"}
            className="size-7"
          >
            {provider ? (
              <ProviderMark providerId={provider.provider_id} />
            ) : (
              <Bot aria-hidden="true" />
            )}
          </ItemMedia>
          <ItemContent>
            <ItemTitle className="text-lg">
              {provider?.name ?? t("No models available")}
            </ItemTitle>
          </ItemContent>
          <ItemActions>
            <Label htmlFor="provider-enabled">{t("Enabled")}</Label>
            <Switch
              id="provider-enabled"
              aria-label={t("Enable provider")}
              checked={draft.is_enabled}
              disabled={blocked}
              onCheckedChange={(checked) => edit({ is_enabled: checked })}
            />
          </ItemActions>
        </Item>

        {loading ? (
          <Alert className="mb-4">
            <Spinner className="text-muted-foreground" />
            <AlertTitle>{t("Loading")}</AlertTitle>
          </Alert>
        ) : loadError ? (
          <Alert variant="destructive" className="mb-4">
            <AlertTitle>{t("Load failed")}</AlertTitle>
            <AlertAction>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (selected) void load();
                  else setReloadKey((value) => value + 1);
                }}
              >
                <RefreshCw />
                {t("Retry")}
              </Button>
            </AlertAction>
          </Alert>
        ) : null}

        <FieldGroup className="gap-3">
          <Field>
            <FieldLabel htmlFor="provider-api-key">API Key</FieldLabel>
            <InputGroup className="bg-muted/50">
              <InputGroupInput
                id="provider-api-key"
                value={draft.key}
                onChange={(event) =>
                  edit({ key: event.target.value, keyEdited: true })
                }
                type={revealKey ? "text" : "password"}
                disabled={blocked}
                placeholder={draft.hasKey ? "••••••••••••••••" : "sk-..."}
                autoComplete="off"
                spellCheck={false}
                aria-describedby="provider-api-key-description"
              />
              <InputGroupAddon align="inline-end">
                <InputGroupButton
                  size="icon-xs"
                  aria-label={revealKey ? t("Hide API Key") : t("Show API Key")}
                  disabled={blocked}
                  onClick={() => setRevealKey(!revealKey)}
                >
                  {revealKey ? <EyeOff /> : <Eye />}
                </InputGroupButton>
                <InputGroupButton
                  size="icon-xs"
                  aria-label={t("Test model connection")}
                  disabled={blocked}
                  onClick={() => void act("test")}
                >
                  {busy === "test" ? <Spinner /> : <Plug />}
                </InputGroupButton>
              </InputGroupAddon>
            </InputGroup>
            <FieldDescription id="provider-api-key-description">
              {t("Your API key is encrypted and stored securely.")}
            </FieldDescription>
          </Field>

        </FieldGroup>

        <Separator className="mt-7" />

        <FieldGroup className="gap-3 pt-5">
          <Item className="px-0 py-0">
            <ItemContent>
              <ItemTitle>{t("Models")}</ItemTitle>
            </ItemContent>
            <ItemActions>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={blocked}
                className="text-muted-foreground"
                onClick={() => void act("discover")}
              >
                {busy === "discover" ? (
                  <>
                    <Spinner />
                    {t("Discovering...")}
                  </>
                ) : (
                  t("Discover models")
                )}
              </Button>
            </ItemActions>
          </Item>

          {draft.models.length ? (
            <ItemGroup className="gap-1">
              {draft.models.map((model) => (
                <Item
                  key={model.model_id}
                  size="sm"
                  className="min-h-11 border-0 hover:bg-muted"
                >
                  <ItemContent className="min-w-0">
                    <ItemTitle title={model.model_id}>
                      {model.model_id}
                    </ItemTitle>
                  </ItemContent>
                  <ItemActions className="ml-auto flex-wrap justify-end">
                    {model.capabilities.map((capability) => (
                      <Badge key={capability} variant="secondary">
                        {capability}
                      </Badge>
                    ))}
                  </ItemActions>
                </Item>
              ))}
            </ItemGroup>
          ) : (
            <Empty className="min-h-28 border-0 p-4">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Bot />
                </EmptyMedia>
                <EmptyTitle>{t("No models available")}</EmptyTitle>
              </EmptyHeader>
            </Empty>
          )}
        </FieldGroup>

        <ItemActions className="mt-auto justify-end pt-10">
          <Button
            type="button"
            disabled={blocked}
            onClick={() => void act("save")}
          >
            {busy === "save" ? (
              <>
                <Spinner />
                {t("Saving...")}
              </>
            ) : (
              t("Save")
            )}
          </Button>
        </ItemActions>
      </FieldGroup>

      <Dialog
        open={candidates !== null}
        onOpenChange={(open) => {
          if (!open) setCandidates(null);
        }}
      >
        <DialogContent
          className="z-[1100] max-w-lg"
          overlayClassName="z-[1090]"
        >
          <DialogHeader>
            <DialogTitle>{t("Select chat models")}</DialogTitle>
            <DialogDescription className="sr-only">
              {t("Select chat models to enable")}
            </DialogDescription>
          </DialogHeader>
          <InputGroup className="my-4">
            <InputGroupAddon>
              <Search />
            </InputGroupAddon>
            <InputGroupInput
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label={t("Search models")}
              placeholder={t("Search models")}
            />
          </InputGroup>
          <ScrollArea className="h-80">
            {filteredCandidates.length ? (
              <ItemGroup className="gap-1 pr-3">
                {filteredCandidates.map((model) => (
                  <Item
                    render={<Label htmlFor={`model-${model.model_id}`} />}
                    key={model.model_id}
                    size="sm"
                    className="cursor-pointer border-0 hover:bg-muted"
                  >
                    <Checkbox
                      id={`model-${model.model_id}`}
                      checked={chosen.includes(model.model_id)}
                      onCheckedChange={(checked) =>
                        setChosen((previous) =>
                          checked === true
                            ? [...previous, model.model_id]
                            : previous.filter((id) => id !== model.model_id),
                        )
                      }
                    />
                    <ItemContent>
                      <ItemTitle>{model.model_id}</ItemTitle>
                    </ItemContent>
                  </Item>
                ))}
              </ItemGroup>
            ) : (
              <Empty className="h-full border-0">
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <Search />
                  </EmptyMedia>
                  <EmptyTitle>{t("No models available")}</EmptyTitle>
                </EmptyHeader>
              </Empty>
            )}
          </ScrollArea>
          <DialogFooter className="border-0 bg-transparent p-0">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setCandidates(null)}
              className="rounded-md px-3 py-2 text-sm hover:bg-accent"
            >
              {t("Cancel")}
            </Button>
            <Button
              type="button"
              className="rounded-md px-4 py-2 text-sm"
              onClick={() => {
                edit({
                  models: (candidates ?? []).filter((model) =>
                    chosen.includes(model.model_id),
                  ),
                });
                setCandidates(null);
              }}
            >
              {t("Confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </FieldGroup>
  );
}
