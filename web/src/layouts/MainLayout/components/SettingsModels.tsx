import { useCallback, useEffect, useRef, useState } from "react";
import { message, Modal } from "antd";
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
        void message.error(error instanceof Error ? error.message : "加载失败");
      }
    } finally {
      if (current === version.current) setLoading(false);
    }
  }, [selected]);
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
      void message.error("请输入 Base URL");
      return;
    }
    if (action === "test" && !draft.models.length) {
      void message.error("请先获取并选择聊天模型");
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
        void (result.cache_refreshed
          ? message.success("已保存")
          : message.warning("已保存，模型缓存刷新失败"));
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
          void message.success(
            `连接成功 · ${Math.round(result.elapsed_ms)} ms`,
          );
        else
          void message.error(
            `连接失败：${result.error ?? "unknown"}${result.status_code ? ` (${result.status_code})` : ""}`,
          );
      }
    } catch (error) {
      if (current === version.current)
        void message.error(error instanceof Error ? error.message : "操作失败");
    } finally {
      if (current === version.current) setBusy(null);
    }
  }
  return (
    <div className="grid min-h-full min-w-0 grid-cols-1 content-start gap-6 min-[1024px]:grid-cols-[176px_minmax(0,1fr)] min-[1024px]:gap-9">
      <nav aria-label="模型供应商" className="min-w-0">
        <div className="flex gap-1 overflow-x-auto pb-1 min-[1024px]:flex-col">
          {providers.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={selected === item.id}
              disabled={busy !== null || candidates !== null}
              className={`flex min-h-11 shrink-0 items-center gap-3 rounded-md px-3 text-left text-sm hover:bg-graphite/5 disabled:opacity-60 ${selected === item.id ? "bg-graphite/5 font-semibold" : "text-slate"}`}
              onClick={() => setSelected(item.id)}
            >
              <img src={item.logo} alt="" className="size-6 object-contain" />
              {item.name}
            </button>
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
          <label className="flex items-center gap-3 text-sm">
            启用{" "}
            <input
              type="checkbox"
              role="switch"
              aria-label="启用供应商"
              checked={draft.is_enabled}
              disabled={blocked}
              onChange={(event) => edit({ is_enabled: event.target.checked })}
            />
          </label>
        </div>
        {(loading || loadError) && (
          <div className="mb-4 flex justify-center">
            {loading ? (
              <LoaderCircle
                size={18}
                className="animate-spin text-slate"
                aria-label="加载中"
              />
            ) : (
              <button
                type="button"
                onClick={() => void load()}
                className="flex items-center gap-2 text-sm text-slate"
              >
                <RefreshCw size={16} />
                重试
              </button>
            )}
          </div>
        )}
        <div className="flex items-center gap-2 rounded-md bg-graphite/[0.025] px-4 py-3">
          <label className="min-w-0 flex-1">
            <span className="mb-1.5 block text-xs text-slate">API Key</span>
            <input
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
              className="w-full bg-transparent text-sm outline-none"
            />
          </label>
          <button
            type="button"
            aria-label={revealKey ? "隐藏 API Key" : "显示 API Key"}
            disabled={blocked}
            onClick={() => setRevealKey(!revealKey)}
          >
            {revealKey ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
          <button
            type="button"
            aria-label="检测模型连接"
            disabled={blocked}
            onClick={() => void act("test")}
          >
            {busy === "test" ? (
              <LoaderCircle size={18} className="animate-spin" />
            ) : (
              <Plug size={18} />
            )}
          </button>
        </div>
        <label className="mt-3 block rounded-md bg-graphite/[0.025] px-4 py-3">
          <span className="mb-1.5 block text-xs text-slate">Base URL</span>
          <input
            value={draft.base_url}
            onChange={(event) => edit({ base_url: event.target.value })}
            type="url"
            disabled={blocked}
            autoComplete="off"
            spellCheck={false}
            className="w-full bg-transparent text-sm outline-none"
          />
        </label>
        <div className="mt-7 border-t border-graphite/8 pt-5">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-sm font-semibold">模型</h4>
            <button
              type="button"
              disabled={blocked}
              className="text-xs text-slate"
              onClick={() => void act("discover")}
            >
              {busy === "discover" ? "获取中..." : "获取模型"}
            </button>
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
          <button
            type="button"
            disabled={blocked}
            className="rounded-md bg-graphite px-5 py-2 text-sm text-white disabled:opacity-40"
            onClick={() => void act("save")}
          >
            {busy === "save" ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
      <Modal
        open={candidates !== null}
        title="选择聊天模型"
        okText="确定"
        cancelText="取消"
        zIndex={1100}
        onOk={() => {
          edit({
            models: (candidates ?? []).filter((model) =>
              chosen.includes(model.model_id),
            ),
          });
          setCandidates(null);
        }}
        onCancel={() => setCandidates(null)}
      >
        <label className="my-4 flex items-center gap-2 rounded bg-graphite/5 px-3 py-2">
          <Search size={16} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="搜索模型"
            placeholder="搜索模型"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none"
          />
        </label>
        <div className="max-h-80 overflow-y-auto">
          {candidates
            ?.filter((model) =>
              model.model_id.toLowerCase().includes(search.toLowerCase()),
            )
            .map((model) => (
              <label
                key={model.model_id}
                className="flex cursor-pointer items-center gap-3 rounded px-2 py-2.5 text-sm hover:bg-graphite/5"
              >
                <input
                  type="checkbox"
                  checked={chosen.includes(model.model_id)}
                  onChange={(event) =>
                    setChosen((previous) =>
                      event.target.checked
                        ? [...previous, model.model_id]
                        : previous.filter((id) => id !== model.model_id),
                    )
                  }
                />
                {model.model_id}
              </label>
            ))}
        </div>
      </Modal>
    </div>
  );
}
