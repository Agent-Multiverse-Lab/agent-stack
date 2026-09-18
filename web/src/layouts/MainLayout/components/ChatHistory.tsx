import { useEffect, useEffectEvent, useRef, useState } from "react";
import { Dropdown, Input, Modal } from "antd";
import { ChevronDown, MoreHorizontal } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router";
import { deleteThread, listThreads, renameThread } from "@/api/agent";
import type { ThreadSummaryResponse } from "@/types/chat";

export default function ChatHistory() {
  const { threadId } = useParams();
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(true);
  const [threads, setThreads] = useState<ThreadSummaryResponse[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<ThreadSummaryResponse | null>(null);
  const [action, setAction] = useState<"rename" | "delete">("rename");
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState("");
  const version = useRef(0);
  async function load(more = false) {
    const next = more ? cursor : undefined;
    if (more && !next) return;
    const current = ++version.current;
    setLoading(true);
    setError("");
    try {
      const result = await listThreads({
        limit: 50,
        cursor: next ?? undefined,
      });
      if (current !== version.current) return;
      setThreads((previous) =>
        more
          ? [
              ...previous,
              ...result.items.filter(
                (item) =>
                  !previous.some(
                    (existing) => existing.thread_id === item.thread_id,
                  ),
              ),
            ]
          : result.items,
      );
      setCursor(result.has_more ? result.next_cursor : null);
    } catch (cause) {
      if (current === version.current)
        setError(cause instanceof Error ? cause.message : "对话加载失败");
    } finally {
      if (current === version.current) setLoading(false);
    }
  }
  const onThreadChange = useEffectEvent(() => void load());
  useEffect(() => {
    onThreadChange();
    const requestVersion = version;
    return () => {
      requestVersion.current++;
    };
  }, [threadId]);
  function openAction(
    thread: ThreadSummaryResponse,
    nextAction: "rename" | "delete",
  ) {
    setSelected(thread);
    setAction(nextAction);
    setTitle(thread.title);
    setActionError("");
  }
  async function submit() {
    if (!selected || saving || (action === "rename" && !title.trim())) return;
    setSaving(true);
    setActionError("");
    try {
      if (action === "rename") {
        const updated = await renameThread(selected.thread_id, title.trim());
        setThreads((previous) =>
          previous.map((item) =>
            item.thread_id === selected.thread_id ? updated : item,
          ),
        );
      } else {
        await deleteThread(selected.thread_id);
        setThreads((previous) =>
          previous.filter((item) => item.thread_id !== selected.thread_id),
        );
        if (threadId === selected.thread_id) navigate("/");
      }
      setSelected(null);
    } catch (cause) {
      setActionError(
        cause instanceof Error ? cause.message : "操作失败，请重试",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <section
        className="flex min-h-0 flex-1 flex-col px-1.5 pt-3 pb-2"
        aria-label="对话历史"
      >
        <button
          type="button"
          className="flex shrink-0 items-center gap-1.5 rounded-sm px-2.5 py-2 text-xs font-medium text-slate hover:bg-graphite/5"
          aria-expanded={expanded}
          aria-controls="sidebar-chat-history"
          onClick={() => setExpanded(!expanded)}
        >
          Chat{" "}
          <ChevronDown size={13} className={expanded ? "" : "-rotate-90"} />
        </button>
        {expanded && (
          <div
            id="sidebar-chat-history"
            className="min-h-0 flex-1 overflow-y-auto overscroll-contain [scrollbar-width:thin]"
            aria-busy={loading}
          >
            {threads.map((thread) => (
              <div
                key={thread.thread_id}
                className={`group flex min-w-0 items-center rounded-sm hover:bg-graphite/5 ${threadId === thread.thread_id ? "bg-graphite/8" : ""}`}
              >
                <Link
                  to={`/c/${encodeURIComponent(thread.thread_id)}`}
                  className="min-w-0 flex-1 truncate rounded-sm px-2.5 py-2 text-sm"
                  title={thread.title}
                  aria-current={
                    threadId === thread.thread_id ? "page" : undefined
                  }
                >
                  {thread.title}
                </Link>
                <Dropdown
                  menu={{
                    items: [
                      { key: "rename", label: "重命名" },
                      { key: "delete", label: "删除对话", danger: true },
                    ],
                    onClick: ({ key }) =>
                      openAction(thread, key as "rename" | "delete"),
                  }}
                  trigger={["click"]}
                  placement="bottomRight"
                >
                  <button
                    type="button"
                    className="mr-1 grid size-8 shrink-0 place-items-center rounded-sm text-slate hover:bg-graphite/8"
                    aria-label={`对话操作：${thread.title}`}
                  >
                    <MoreHorizontal size={16} />
                  </button>
                </Dropdown>
              </div>
            ))}
            {error && (
              <>
                <p role="alert" className="px-2.5 py-2 text-xs text-danger">
                  {error}
                </p>
                <button
                  type="button"
                  className="px-2.5 py-2 text-xs hover:underline"
                  onClick={() => void load(Boolean(cursor))}
                >
                  重试
                </button>
              </>
            )}
            {!error && loading && (
              <p role="status" className="px-2.5 py-2 text-xs text-slate">
                加载中…
              </p>
            )}
            {!error && !loading && !threads.length && (
              <p className="px-2.5 py-2 text-xs text-slate">暂无对话</p>
            )}
            {cursor && !loading && !error && (
              <button
                type="button"
                className="w-full rounded-sm px-2.5 py-2 text-left text-xs text-slate hover:bg-graphite/5"
                onClick={() => void load(true)}
              >
                加载更多
              </button>
            )}
          </div>
        )}
      </section>
      <Modal
        open={selected !== null}
        title={action === "rename" ? "重命名对话" : "删除对话"}
        okText={action === "rename" ? "保存" : "删除"}
        cancelText="取消"
        confirmLoading={saving}
        closable={!saving}
        maskClosable={!saving}
        keyboard={!saving}
        okButtonProps={{
          danger: action === "delete",
          disabled: action === "rename" && !title.trim(),
        }}
        onCancel={() => setSelected(null)}
        onOk={() => void submit()}
      >
        {action === "rename" ? (
          <Input
            value={title}
            aria-label="对话标题"
            disabled={saving}
            onChange={(event) => setTitle(event.target.value)}
            onPressEnter={() => void submit()}
          />
        ) : (
          <p className="break-words">
            确定删除「{selected?.title}」吗？删除后该对话将从历史列表中移除。
          </p>
        )}
        {actionError && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {actionError}
          </p>
        )}
      </Modal>
    </>
  );
}
