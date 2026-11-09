import { useCallback, useEffect, useRef, useState } from "react"
import { Bot, Eye, EyeOff, Plug, RefreshCw, Search } from "lucide-react"
import { toast } from "sonner"

import {
  discoverProviderModels,
  getModelProvider,
  listModelProviders,
  saveModelProvider,
  testProviderConnection,
} from "@/api/model"
import type { ModelSettingsRequest } from "@/api/model"
import chatgptLogo from "@/assets/models/chatgpt-color.svg"
import deepseekLogo from "@/assets/models/deepseek-color.svg"
import geminiLogo from "@/assets/models/gemini-color.svg"
import minimaxLogo from "@/assets/models/minimax-color.svg"
import ollamaLogo from "@/assets/models/ollama-color.svg"
import openaiLogo from "@/assets/models/openai.svg"
import qwenLogo from "@/assets/models/qwen-color.svg"
import vllmLogo from "@/assets/models/vllm-color.svg"
import zhipuLogo from "@/assets/models/zhipu-color.svg"
import { Alert, AlertAction, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemGroup,
  ItemTitle,
} from "@/components/ui/item"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { useAuth } from "@/context/AuthContext"
import { useTranslation } from "@/i18n"
import { SettingsModelOption } from "@/layouts/MainLayout/components/SettingsModelOption"
import type {
  ModelProvider,
  ModelProviderId,
  ModelProviderMetadata,
  SettingsModel,
} from "@/types/model"

const providerLogos: Record<string, string> = {
  deepseek: deepseekLogo,
  dashscope: qwenLogo,
  qwen: qwenLogo,
  openai: openaiLogo,
  chatgpt: chatgptLogo,
  gemini: geminiLogo,
  zhipu: zhipuLogo,
  glm: zhipuLogo,
  minimax: minimaxLogo,
  ollama: ollamaLogo,
  vllm: vllmLogo,
}

function ProviderMark({ providerId }: { providerId: string }) {
  const logo = providerLogos[providerId.toLowerCase()]
  return (
    <span className="flex size-8 shrink-0 items-center justify-center rounded-[7px] border border-border/60 bg-muted/40 p-1.5">
      {logo ? (
        <img src={logo} alt="" className="size-full object-contain" />
      ) : (
        <Bot aria-hidden="true" className="size-4 text-muted-foreground" />
      )}
    </span>
  )
}

interface Draft extends ModelSettingsRequest {
  key: string
  keyEdited: boolean
  hasKey: boolean
  initialized: boolean
}

const emptyDraft = (): Draft => ({
  base_url: "",
  is_enabled: false,
  models: [],
  key: "",
  keyEdited: false,
  hasKey: false,
  initialized: false,
})

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
})

export function ModelProviderCards() {
  const { t, i18n } = useTranslation()
  const { accessToken } = useAuth()
  const [providers, setProviders] = useState<ModelProviderMetadata[]>([])
  const [selected, setSelected] = useState<ModelProviderId>("")
  const [dialogOpen, setDialogOpen] = useState(false)
  const [drafts, setDrafts] = useState<Partial<Record<string, Draft>>>({})
  const draft = drafts[selected] ?? emptyDraft()
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState("")
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState(false)
  const [busy, setBusy] = useState<"save" | "discover" | "test" | null>(null)
  const [candidates, setCandidates] = useState<SettingsModel[] | null>(null)
  const [chosen, setChosen] = useState<string[]>([])
  const [search, setSearch] = useState("")
  const [revealKey, setRevealKey] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const version = useRef(0)

  const provider = providers.find((item) => item.provider_id === selected)
  const blocked = detailLoading || detailError || busy !== null || !provider
  const filteredCandidates =
    candidates?.filter((model) =>
      model.model_id.toLowerCase().includes(search.toLowerCase())
    ) ?? []

  function edit(patch: Partial<Draft>) {
    if (!selected) return
    setDrafts((previous) => ({
      ...previous,
      [selected]: { ...(previous[selected] ?? emptyDraft()), ...patch },
    }))
  }

  const loadDetail = useCallback(
    async (providerId: ModelProviderId, force = false) => {
      if (!providerId) return
      const current = ++version.current
      setDetailLoading(true)
      setDetailError(false)
      try {
        const value = await getModelProvider(providerId)
        if (current !== version.current) return
        setDrafts((previous) =>
          !force && previous[providerId]?.initialized
            ? previous
            : {
                ...previous,
                [providerId]: providerDraft(value),
              }
        )
      } catch (error) {
        if (current === version.current) {
          setDetailError(true)
          toast.error(error instanceof Error ? error.message : i18n.t("Load failed"))
        }
      } finally {
        if (current === version.current) setDetailLoading(false)
      }
    },
    [i18n]
  )

  useEffect(() => {
    let cancelled = false
    const current = ++version.current
    setProviders([])
    setSelected("")
    setDialogOpen(false)
    setDrafts({})
    setCandidates(null)
    setChosen([])
    setSearch("")
    setRevealKey(false)
    setListError("")
    setDetailError(false)
    if (!accessToken) {
      setListLoading(false)
      return
    }
    setListLoading(true)
    void listModelProviders()
      .then((items) => {
        if (cancelled || current !== version.current) return
        setProviders(items)
        setListLoading(false)
        for (const item of items) {
          void getModelProvider(item.provider_id)
            .then((detail) => {
              if (cancelled || current !== version.current) return
              setDrafts((previous) =>
                previous[item.provider_id]?.initialized
                  ? previous
                  : {
                      ...previous,
                      [item.provider_id]: providerDraft(detail),
                    }
              )
            })
            .catch(() => {})
        }
      })
      .catch((error: unknown) => {
        if (cancelled || current !== version.current) return
        const message = error instanceof Error ? error.message : i18n.t("Load failed")
        setListError(message)
        setListLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [accessToken, i18n, reloadKey])

  function handleOpenProvider(providerId: ModelProviderId) {
    setSelected(providerId)
    setRevealKey(false)
    setDetailError(false)
    setDialogOpen(true)
    if (!drafts[providerId]?.initialized) {
      void loadDetail(providerId)
    }
  }

  function request(): ModelSettingsRequest {
    return {
      base_url: draft.base_url,
      is_enabled: draft.is_enabled,
      models: draft.models.map((model) => ({
        ...model,
        capabilities: [...model.capabilities],
      })),
      ...(draft.keyEdited ? { api_key: draft.key } : {}),
    }
  }

  async function act(action: "save" | "discover" | "test") {
    if (blocked || !selected) return
    const current = version.current
    const body = request()
    setBusy(action)
    try {
      if (action === "save") {
        const result = await saveModelProvider(selected, body)
        if (current !== version.current) return
        let saved: ModelProvider
        try {
          saved = await getModelProvider(selected)
        } catch {
          if (current !== version.current) return
          edit({ key: "", keyEdited: false })
          toast.warning(t("Saved, but reloading the provider failed"))
          return
        }
        if (current !== version.current) return
        setDrafts((previous) => ({
          ...previous,
          [selected]: providerDraft(saved),
        }))
        setProviders((previous) =>
          previous.map((item) =>
            item.provider_id === selected
              ? {
                  ...item,
                  is_enabled: saved.is_enabled,
                  has_api_key: saved.has_api_key,
                }
              : item
          )
        )
        if (result.cache_refreshed) toast.success(t("Saved"))
        else toast.warning(t("Saved, but refreshing the model cache failed"))
        setDialogOpen(false)
      } else if (action === "discover") {
        const result = await discoverProviderModels(selected, body)
        if (current !== version.current) return
        setCandidates([
          ...new Map(
            [...body.models, ...result].map((model) => [model.model_id, model])
          ).values(),
        ])
        setChosen(body.models.map((model) => model.model_id))
        setSearch("")
      } else {
        const result = await testProviderConnection(selected, body)
        if (current !== version.current) return
        if (result.success) {
          toast.success(
            t("Connection succeeded · {{ms}} ms", {
              ms: Math.round(result.elapsed_ms),
            })
          )
        } else {
          toast.error(
            `${t("Connection failed: {{error}}", {
              error: result.error ?? "unknown",
            })}${result.status_code ? ` (${result.status_code})` : ""}`
          )
        }
      }
    } catch (error) {
      if (current === version.current) {
        toast.error(error instanceof Error ? error.message : t("Operation failed"))
      }
    } finally {
      if (current === version.current) setBusy(null)
    }
  }

  if (listLoading) {
    return (
      <div
        className="flex min-h-48 items-center justify-center gap-2 text-sm text-muted-foreground"
        role="status"
      >
        <Spinner className="size-5" />
        {t("Loading...")}
      </div>
    )
  }

  if (listError) {
    return (
      <div
        className="flex min-h-48 flex-col items-center justify-center gap-3 text-center"
        role="alert"
      >
        <p className="text-sm font-medium">{t("Load failed")}</p>
        <p className="max-w-lg text-sm text-muted-foreground">{listError}</p>
        <Button variant="outline" onClick={() => setReloadKey((value) => value + 1)}>
          {t("Retry")}
        </Button>
      </div>
    )
  }

  if (!providers.length) {
    return (
      <Empty className="min-h-48">
        <EmptyMedia>
          <Bot aria-hidden="true" />
        </EmptyMedia>
        <EmptyTitle>{t("No models available")}</EmptyTitle>
      </Empty>
    )
  }

  return (
    <>
      <section className="space-y-3" aria-labelledby="model-providers-heading">
        <h2 id="model-providers-heading" className="flex items-center gap-2 text-sm font-medium">
          {t("Model providers")} <Badge>{providers.length}</Badge>
        </h2>
        <ul
          aria-label={t("Model providers")}
          className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr))]"
        >
          {providers.map((item) => {
            const itemDraft = drafts[item.provider_id]
            const isEnabled = itemDraft?.initialized ? itemDraft.is_enabled : item.is_enabled
            const hasKey = itemDraft?.initialized ? itemDraft.hasKey : item.has_api_key
            const models = itemDraft?.models ?? []
            const previewModels = models.slice(0, 3)
            const remainingCount = models.length - previewModels.length

            return (
              <li key={item.provider_id} className="h-full">
                <article aria-label={item.name} className="h-full">
                  <Card className="relative h-full cursor-pointer gap-2.5 rounded-lg p-4 hover:border-input hover:bg-muted">
                    <CardHeader className="p-0">
                      <div className="flex min-w-0 items-center justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-2.5">
                          <ProviderMark providerId={item.provider_id} />
                          <h3 className="truncate text-sm font-semibold">{item.name}</h3>
                        </div>
                        <Badge variant={isEnabled ? "success" : "default"} className="shrink-0">
                          {t(isEnabled ? "Enabled" : "Disabled")}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="p-0">
                      {models.length > 0 ? (
                        <div className="flex min-h-[2.8em] flex-wrap content-start items-center gap-1.5">
                          {previewModels.map((model) => (
                            <Badge
                              key={model.model_id}
                              variant="secondary"
                              className="max-w-full truncate rounded-md px-2 py-0.5 font-mono text-xs font-normal"
                            >
                              {model.model_id}
                            </Badge>
                          ))}
                          {remainingCount > 0 && (
                            <Badge
                              variant="outline"
                              className="rounded-md px-1.5 py-0.5 text-xs font-normal tabular-nums"
                            >
                              +{remainingCount}
                            </Badge>
                          )}
                        </div>
                      ) : (
                        <p className="line-clamp-2 min-h-[2.8em] text-[13px] leading-[1.4] text-muted-foreground">
                          {hasKey ? t("No models available") : t("Not configured")}
                        </p>
                      )}
                    </CardContent>
                    <Button
                      type="button"
                      variant="ghost"
                      aria-label={item.name}
                      onClick={() => handleOpenProvider(item.provider_id)}
                      className="absolute inset-0 z-10 h-full w-full rounded-lg border-0 p-0 hover:bg-transparent focus-visible:ring-inset"
                    />
                  </Card>
                </article>
              </li>
            )
          })}
        </ul>
      </section>

      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          if (busy !== null) return
          if (!open) {
            setCandidates(null)
            setDialogOpen(false)
          }
        }}
      >
        <DialogContent
          className="z-[100] flex max-h-[min(680px,calc(100dvh-48px))] w-[calc(100vw-32px)] max-w-lg flex-col gap-0 overflow-hidden p-0"
          overlayClassName="z-[90]"
        >
          <DialogHeader className="shrink-0 border-b border-border px-6 py-4 pr-12">
            <div className="flex items-center justify-between gap-4">
              <div className="flex min-w-0 items-center gap-2.5">
                {provider && <ProviderMark providerId={provider.provider_id} />}
                <DialogTitle className="truncate text-base font-semibold">
                  {provider?.name ?? t("Models")}
                </DialogTitle>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Label htmlFor="provider-enabled" className="text-xs text-muted-foreground">
                  {t("Enabled")}
                </Label>
                <Switch
                  id="provider-enabled"
                  aria-label={t("Enable provider")}
                  checked={draft.is_enabled}
                  disabled={blocked}
                  onCheckedChange={(checked) => edit({ is_enabled: checked })}
                />
              </div>
            </div>
            <DialogDescription className="sr-only">
              {provider?.name ?? t("Model providers")}
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 overflow-y-auto p-6" aria-busy={detailLoading}>
            {detailLoading ? (
              <Alert className="mb-4">
                <Spinner className="text-muted-foreground" />
                <AlertTitle>{t("Loading")}</AlertTitle>
              </Alert>
            ) : detailError ? (
              <Alert variant="destructive" className="mb-4">
                <AlertTitle>{t("Load failed")}</AlertTitle>
                <AlertAction>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => void loadDetail(selected, true)}
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
                <InputGroup>
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
              </Field>
            </FieldGroup>

            <Separator className="my-4" />

            <FieldGroup className="gap-3">
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
                <ScrollArea className="max-h-60">
                  <ItemGroup aria-label={t("Configured models")} className="gap-2 pr-2">
                    {draft.models.map((model) => (
                      <SettingsModelOption
                        key={model.model_id}
                        model={model}
                        isDisabled={blocked}
                      />
                    ))}
                  </ItemGroup>
                </ScrollArea>
              ) : (
                <Empty className="min-h-24 border-0 p-3">
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <Bot />
                    </EmptyMedia>
                    <EmptyTitle>{t("No models available")}</EmptyTitle>
                  </EmptyHeader>
                </Empty>
              )}
            </FieldGroup>
          </div>

          <DialogFooter className="shrink-0 flex-row justify-end gap-2 border-t border-border px-6 py-4">
            <Button
              type="button"
              variant="outline"
              disabled={busy !== null}
              onClick={() => setDialogOpen(false)}
            >
              {t("Cancel")}
            </Button>
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
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={candidates !== null}
        onOpenChange={(open) => {
          if (!open) setCandidates(null)
        }}
      >
        <DialogContent
          className="z-[1100] max-w-md p-5"
          overlayClassName="z-[1090]"
        >
          <DialogHeader>
            <DialogTitle className="text-sm font-semibold">
              {t("Select chat models")}
            </DialogTitle>
            <DialogDescription className="sr-only">
              {t("Select chat models to enable")}
            </DialogDescription>
          </DialogHeader>
          <InputGroup className="my-3 h-8 text-xs">
            <InputGroupAddon>
              <Search className="size-3.5" />
            </InputGroupAddon>
            <InputGroupInput
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label={t("Search models")}
              placeholder={t("Search models")}
              className="h-8 text-xs"
            />
          </InputGroup>
          <ScrollArea className="h-72">
            {filteredCandidates.length ? (
              <ItemGroup aria-label={t("Available models")} className="gap-1.5 pr-2">
                {filteredCandidates.map((model) => (
                  <SettingsModelOption
                    key={model.model_id}
                    model={model}
                    isSelected={chosen.includes(model.model_id)}
                    isDisabled={busy !== null}
                    onSelectedChange={(isSelected) =>
                      setChosen((previous) =>
                        isSelected
                          ? [...previous, model.model_id]
                          : previous.filter((id) => id !== model.model_id)
                      )
                    }
                  />
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
                    chosen.includes(model.model_id)
                  ),
                })
                setCandidates(null)
              }}
            >
              {t("Confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
