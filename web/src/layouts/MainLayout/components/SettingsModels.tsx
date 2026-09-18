import { Label } from "@/components/ui/label";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
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
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Eye,
  EyeOff,
  LoaderCircle,
  Plug,
  RefreshCw,
  Search,
} from "lucide-react";
import deepseekLogo from "@/assets/models/deepseek-color.svg";
import qwenLogo from "@/assets/models/qwen-color.svg";
import glmLogo from "@/assets/models/zhipu-color.svg";
import minimaxLogo from "@/assets/models/minimax-color.svg";
import geminiLogo from "@/assets/models/gemini-color.svg";
import chatgptLogo from "@/assets/models/chatgpt-color.svg";
import ollamaLogo from "@/assets/models/ollama-color.svg";
import vllmLogo from "@/assets/models/vllm-color.svg";
import {
  discoverProviderModels,
  getModelProvider,
  saveModelProvider,
  testProviderConnection,
} from "@/api/model";
import { useAuth } from "@/context/AuthContext";
import { useTranslation } from "@/i18n";
import type {
  ModelProviderId,
  ModelSettingsRequest,
  SettingsModel,
} from "@/types/model";

const providers: { id: ModelProviderId; name: string; logo: string }[] = [
  { id: "deepseek", name: "DeepSeek", logo: deepseekLogo },
  { id: "qwen", name: "Qwen", logo: qwenLogo },
  { id: "glm", name: "GLM", logo: glmLogo },
  { id: "minomax", name: "minomax", logo: minimaxLogo },
  { id: "gemini", name: "Gemini", logo: geminiLogo },
  { id: "chatgpt", name: "ChatGPT", logo: chatgptLogo },
  { id: "ollama", name: "Ollama", logo: ollamaLogo },
  { id: "vllm", name: "vLLM", logo: vllmLogo },
];
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

export default function SettingsModels() {
  const { t, i18n } = useTranslation();
  const { accessToken } = useAuth();
  const [selected, setSelected] = useState<ModelProviderId>("deepseek");
  const [drafts, setDrafts] = useState<Partial<Record<ModelProviderId, Draft>>>(
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
  const version = useRef(0);
  const blocked = loading || loadError || busy !== null;
  const provider = providers.find((item) => item.id === selected)!;
  function edit(patch: Partial<Draft>) {
    setDrafts((previous) => ({
      ...previous,
      [selected]: { ...(previous[selected] ?? emptyDraft()), ...patch },
    }));
  }
  const load = useCallback(async () => {
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
              [selected]: {
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
              },
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
    void load();
    const requestVersion = version;
    return () => {
      requestVersion.current++;
    };
  }, [load, accessToken]);
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
    if (blocked) return;
    if (!draft.base_url.trim()) {
      toast.error(t("Enter a Base URL"));
      return;
    }
    if (action === "test" && !draft.models.length) {
      toast.error(t("Discover and select a chat model first"));
      return;
    }
    const current = version.current;
    const body = request();
    setBusy(action);
    try {
      if (action === "save") {
        const result = await saveModelProvider(selected, body);
        if (current !== version.current) return;
        edit({
          key: "",
          keyEdited: false,
          hasKey: draft.keyEdited ? Boolean(draft.key) : draft.hasKey,
          initialized: true,
        });
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
    <div className="grid min-h-full min-w-0 grid-cols-1 content-start gap-6 min-[1024px]:grid-cols-[176px_minmax(0,1fr)] min-[1024px]:gap-9">
      <nav aria-label={t("Model providers")} className="min-w-0">
        <div className="flex gap-1 overflow-x-auto pb-1 min-[1024px]:flex-col">
          {providers.map((item) => (
            <Button
              key={item.id}
              type="button"
              variant="ghost"
              aria-pressed={selected === item.id}
              disabled={busy !== null || candidates !== null}
              className={`min-h-11 shrink-0 justify-start gap-3 rounded-md px-3 text-left text-sm hover:bg-graphite/5 disabled:opacity-60 ${selected === item.id ? "bg-graphite/5 font-semibold" : "text-slate"}`}
              onClick={() => setSelected(item.id)}
            >
              <img src={item.logo} alt="" className="size-6 object-contain" />
              {item.name}
            </Button>
          ))}
        </div>
      </nav>
      <div
        className="flex min-w-0 flex-col min-[1024px]:min-h-[490px]"
        aria-busy={loading}
      >
        <div className="mb-7 flex items-center justify-between">
          <h3 className="flex items-center gap-3 text-lg font-semibold">
            <img src={provider.logo} alt="" className="size-7" />
            {provider.name}
          </h3>
          <div className="flex items-center gap-3 text-sm">
            {t("Enabled")}{" "}
            <Switch
              aria-label={t("Enable provider")}
              checked={draft.is_enabled}
              disabled={blocked}
              onCheckedChange={(checked) => edit({ is_enabled: checked })}
            />
          </div>
        </div>
        {(loading || loadError) && (
          <div className="mb-4 flex justify-center">
            {loading ? (
              <LoaderCircle
                size={18}
                className="animate-spin text-slate"
                aria-label={t("Loading")}
              />
            ) : (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => void load()}
                className="gap-2 text-sm text-slate"
              >
                <RefreshCw size={16} />
                {t("Retry")}
              </Button>
            )}
          </div>
        )}
        <div className="flex items-center gap-2 rounded-md bg-graphite/[0.025] px-4 py-3">
          <Label className="block min-w-0 flex-1">
            <span className="mb-1.5 block text-xs text-slate">API Key</span>
            <Input
              value={draft.key}
              onChange={(event) =>
                edit({ key: event.target.value, keyEdited: true })
              }
              type={revealKey ? "text" : "password"}
              disabled={blocked}
              placeholder={draft.hasKey ? "••••••••••••••••" : ""}
              autoComplete="off"
              spellCheck={false}
              aria-label="API Key"
              className="w-full border-0 bg-transparent px-0 text-sm focus-visible:ring-0"
            />
          </Label>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={revealKey ? t("Hide API Key") : t("Show API Key")}
            disabled={blocked}
            onClick={() => setRevealKey(!revealKey)}
          >
            {revealKey ? <EyeOff size={18} /> : <Eye size={18} />}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={t("Test model connection")}
            disabled={blocked}
            onClick={() => void act("test")}
          >
            {busy === "test" ? (
              <LoaderCircle size={18} className="animate-spin" />
            ) : (
              <Plug size={18} />
            )}
          </Button>
        </div>
        <Label className="mt-3 block rounded-md bg-graphite/[0.025] px-4 py-3">
          <span className="mb-1.5 block text-xs text-slate">Base URL</span>
          <Input
            value={draft.base_url}
            onChange={(event) => edit({ base_url: event.target.value })}
            type="url"
            disabled={blocked}
            autoComplete="off"
            spellCheck={false}
            className="w-full border-0 bg-transparent px-0 text-sm focus-visible:ring-0"
          />
        </Label>
        <div className="mt-7 border-t border-graphite/8 pt-5">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-sm font-semibold">{t("Models")}</h4>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={blocked}
              className="text-xs text-slate"
              onClick={() => void act("discover")}
            >
              {busy === "discover" ? t("Discovering...") : t("Discover models")}
            </Button>
          </div>
          <ul>
            {draft.models.map((model) => (
              <li
                key={model.model_id}
                className="flex min-h-11 items-center gap-3 rounded-md px-2.5 py-2 text-sm hover:bg-graphite/5"
              >
                <span className="min-w-0 truncate" title={model.model_id}>
                  {model.model_id}
                </span>
                <span className="ml-auto text-xs text-slate">
                  {model.capabilities.join(" · ")}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="mt-auto flex justify-end pt-10">
          <Button
            type="button"
            disabled={blocked}
            className="bg-graphite px-5 text-sm text-white hover:bg-graphite/90"
            onClick={() => void act("save")}
          >
            {busy === "save" ? t("Saving...") : t("Save")}
          </Button>
        </div>
      </div>
      <Dialog
        open={candidates !== null}
        onOpenChange={(open) => {
          if (!open) setCandidates(null);
        }}
      >
        <DialogContent
          className="z-[1100] sm:max-w-lg"
          overlayClassName="z-[1090]"
        >
          <DialogHeader>
            <DialogTitle>{t("Select chat models")}</DialogTitle>
            <DialogDescription className="sr-only">{t("Select chat models to enable")}</DialogDescription>
          </DialogHeader>
          <Label className="my-4 flex items-center gap-2 rounded bg-graphite/5 px-3 py-2">
            <Search size={16} />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label={t("Search models")}
              placeholder={t("Search models")}
              className="min-w-0 flex-1 border-0 bg-transparent px-0 text-sm focus-visible:ring-0"
            />
          </Label>
          <div className="max-h-80 overflow-y-auto">
            {candidates
              ?.filter((model) =>
                model.model_id.toLowerCase().includes(search.toLowerCase()),
              )
              .map((model) => (
                <Label
                  key={model.model_id}
                  className="flex cursor-pointer items-center gap-3 rounded px-2 py-2.5 text-sm hover:bg-graphite/5"
                >
                  <Checkbox
                    checked={chosen.includes(model.model_id)}
                    onCheckedChange={(checked) =>
                      setChosen((previous) =>
                        checked
                          ? [...previous, model.model_id]
                          : previous.filter((id) => id !== model.model_id),
                      )
                    }
                  />
                  {model.model_id}
                </Label>
              ))}
          </div>
          <DialogFooter className="border-0 bg-transparent p-0">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setCandidates(null)}
              className="rounded-md px-3 py-2 text-sm hover:bg-mist"
            >
              {t("Cancel")}
            </Button>
            <Button
              type="button"
              className="rounded-md bg-graphite px-4 py-2 text-sm text-white"
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
    </div>
  );
}
