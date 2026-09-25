import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  Plus,
  ArrowUp,
  Paperclip,
  Globe2,
  SlidersHorizontal,
  MessageSquare,
  Trash2,
  Download,
  LogOut,
  Menu,
  X,
  Square,
  ArrowUpRight,
  LoaderCircle,
  BookOpen,
  GitCompareArrows,
  Lightbulb,
  Check,
} from "lucide-react";
import { Brand } from "./Auth";
import SettingsPanel from "./Settings";
const AdminDashboard = lazy(() => import("./AdminDashboard"));
const ResultView = lazy(() => import("./ResultView"));
import { request, download } from "../lib/api";
import { useRun } from "../lib/useRun";
import type {
  User,
  Model,
  Conversation,
  ConversationSummary,
  Settings,
  Document,
  Run,
  Result,
} from "../lib/types";

const defaults: Settings = {
  mode: "auto",
  panel_size: 4,
  debate_rounds: 2,
  web_search_enabled: false,
  enabled_models: [],
};
const suggestions = [
  {
    icon: Lightbulb,
    label: "Explore an idea",
    text: "Explain an idea from two different perspectives",
    prompt:
      "Explain how a small team can make better decisions. Compare two approaches and their trade-offs.",
  },
  {
    icon: GitCompareArrows,
    label: "Compare options",
    text: "See the strengths, gaps, and trade-offs",
    prompt:
      "Compare building a small web app with a simple monolith versus separate services. Include trade-offs.",
  },
  {
    icon: BookOpen,
    label: "Make sense of it",
    text: "Turn a complicated topic into a clear answer",
    prompt:
      "Explain how large language models work, with an intuitive example and their limitations.",
  },
];

export default function Workspace({
  user,
  logout,
}: {
  user: User;
  logout: () => void;
}) {
  const [adminOpen, setAdminOpen] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [settings, setSettings] = useState<Settings>(defaults);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [input, setInput] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [ready, setReady] = useState(false);
  const [filter, setFilter] = useState("");
  const currentId = useRef<string | null>(null);
  const navigation = useRef(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const nearEnd = useRef(true);
  const activeRequestKey = useRef<string | null>(null);
  const reloadList = useCallback(async () => {
    setConversations(await request<ConversationSummary[]>("/conversations"));
  }, []);
  const load = useCallback(async (id: string) => {
    const version = ++navigation.current;
    currentId.current = id;
    setRunId(null);
    setError("");
    setNotice("");
    setSidebarOpen(false);
    setConversation(null);
    try {
      const conv = await request<Conversation>(`/conversations/${id}`);
      if (version !== navigation.current) return;
      setConversation(conv);
      setRunId(conv.active_run_id || null);
      nearEnd.current = true;
    } catch (e) {
      if (version === navigation.current)
        setError(
          e instanceof Error ? e.message : "Could not load conversation",
        );
    }
  }, []);
  useEffect(() => {
    let active = true;
    Promise.all([
      request<Model[]>("/models"),
      request<ConversationSummary[]>("/conversations"),
    ])
      .then(([list, convs]) => {
        if (!active) return;
        setModels(list);
        setConversations(convs);
        let saved: Partial<Settings> = {};
        try {
          saved = JSON.parse(
            localStorage.getItem(`convene-settings-${user.id}`) || "{}",
          );
        } catch {
          /* Use defaults. */
        }
        const ids = new Set(
          list
            .filter((m) => m.status === "active" && m.configured)
            .map((m) => m.id),
        );
        setSettings({
          ...defaults,
          ...saved,
          enabled_models: Array.isArray(saved.enabled_models)
            ? saved.enabled_models.filter((id) => ids.has(id))
            : [...ids],
        });
        setReady(true);
      })
      .catch(() => {
        if (active)
          setError(
            "Could not load your workspace. The server may be waking up. Refresh in a moment.",
          );
      });
    return () => {
      active = false;
    };
  }, [user.id]);
  function changeSettings(next: Settings) {
    if (!ready) return;
    setSettings(next);
    localStorage.setItem(`convene-settings-${user.id}`, JSON.stringify(next));
  }
  const finished = useCallback(
    (result: Result, status: string) => {
      setRunId(null);
      if (status !== "complete")
        setNotice(result.notice || `This answer is ${status}.`);
      const id = currentId.current;
      if (id)
        request<Conversation>(`/conversations/${id}`)
          .then((conv) => {
            if (currentId.current === id) setConversation(conv);
          })
          .catch(() =>
            setError(
              "The answer was saved, but could not be reloaded. Open this conversation again.",
            ),
          );
      void reloadList().catch(() => undefined);
      void request<Model[]>("/models")
        .then(setModels)
        .catch(() => undefined);
    },
    [reloadList],
  );
  const run = useRun(runId, finished);
  useEffect(() => {
    if (nearEnd.current)
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [conversation?.messages.length, run.result.content, runId]);
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height =
        Math.min(inputRef.current.scrollHeight, 170) + "px";
    }
  }, [input]);
  function fresh() {
    navigation.current++;
    currentId.current = null;
    setConversation(null);
    setRunId(null);
    setInput("");
    setDocuments([]);
    setError("");
    setNotice("");
    setSidebarOpen(false);
    activeRequestKey.current = null;
    inputRef.current?.focus();
  }
  async function send(e: FormEvent) {
    e.preventDefault();
    if (!ready || !input.trim() || submitting || runId || uploading) return;
    if (!settings.enabled_models.length) {
      setError("Choose at least one model in Council settings.");
      return;
    }
    setSubmitting(true);
    setError("");
    setNotice("");
    const version = navigation.current;
    try {
      let id = currentId.current;
      if (!id) {
        const created = await request<ConversationSummary>("/conversations", {
          method: "POST",
        });
        id = created.id;
        currentId.current = id;
      }
      activeRequestKey.current ||= crypto.randomUUID();
      const response = await request<Run>(`/conversations/${id}/runs`, {
        method: "POST",
        body: JSON.stringify({
          ...settings,
          content: input.trim(),
          documents,
          request_key: activeRequestKey.current,
        }),
      });
      if (version !== navigation.current) {
        void reloadList();
        return;
      }
      activeRequestKey.current = null;
      setInput("");
      setDocuments([]);
      const conv = await request<Conversation>(`/conversations/${id}`);
      setConversation(conv);
      setRunId(
        ["queued", "running"].includes(response.status)
          ? response.id
          : conv.active_run_id || null,
      );
      nearEnd.current = true;
      await reloadList();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Your question could not be sent. Try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }
  async function remove(id: string) {
    try {
      await request(`/conversations/${id}`, { method: "DELETE" });
      if (currentId.current === id) fresh();
      await reloadList();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not delete conversation",
      );
    }
  }
  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setError("");
    if (files.length + documents.length > 3) {
      setError("Attach at most three documents.");
      return;
    }
    if ([...files].some((f) => f.size > 5 * 1024 * 1024)) {
      setError("Each document must be smaller than 5 MB.");
      return;
    }
    setUploading(true);
    const form = new FormData();
    [...files].forEach((f) => form.append("files", f));
    try {
      const data = await request<{ files: Document[] }>("/files/parse", {
        method: "POST",
        body: form,
      });
      setDocuments((prev) => [...prev, ...data.files]);
      if (data.files.some((f) => f.truncated))
        setNotice("Long documents were shortened to fit the context.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read the document");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }
  async function stop() {
    if (runId)
      try {
        await request(`/runs/${runId}/cancel`, { method: "POST" });
      } catch {
        setError("Could not stop the answer. Please try again.");
      }
  }
  if (adminOpen && user.is_admin)
    return (
      <Suspense
        fallback={<div className="loading-page">Loading dashboard…</div>}
      >
        <AdminDashboard close={() => setAdminOpen(false)} />
      </Suspense>
    );
  const empty = !conversation?.messages.length && !runId;
  return (
    <div className="workspace">
      {sidebarOpen && (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-brand">
          <Brand />
          <button
            className="icon-button mobile-only"
            aria-label="Close navigation"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <button className="new-chat" onClick={fresh} disabled={submitting}>
          <Plus size={18} /> New conversation <span>＋</span>
        </button>
        <div className="sidebar-section">
          <span>YOUR CONVERSATIONS</span>
          <span>{conversations.length.toString().padStart(2, "0")}</span>
        </div>
        <label className="sr-only" htmlFor="conversation-filter">
          Search conversations
        </label>
        <input
          id="conversation-filter"
          className="conversation-filter"
          placeholder="Find a conversation…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <nav className="conversation-list" aria-label="Conversations">
          {conversations
            .filter((c) => c.title.toLowerCase().includes(filter.toLowerCase()))
            .map((c) => (
              <div
                className={`conversation-item ${conversation?.id === c.id ? "active" : ""}`}
                key={c.id}
              >
                <button onClick={() => void load(c.id)} disabled={submitting}>
                  <MessageSquare size={15} />
                  <span>{c.title}</span>
                  {c.active_run_id && <span className="live-dot" />}
                </button>
                <button
                  className="delete-chat icon-button"
                  aria-label={`Delete ${c.title}`}
                  onClick={() => void remove(c.id)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          {!conversations.length && (
            <p className="sidebar-empty">
              A fresh space for your ideas.
              <br />
              Your conversations will appear here.
            </p>
          )}
        </nav>
        <div className="sidebar-bottom">
          {user.is_admin && (
            <button
              className="sidebar-settings"
              onClick={() => setAdminOpen(true)}
            >
              Admin dashboard
            </button>
          )}
          <div className="workspace-note">
            <span className="model-dot" />
            <div>
              <strong>A meeting of minds</strong>
              <span>Independent models. One clear answer.</span>
            </div>
          </div>
          <button
            className="sidebar-settings"
            disabled={!ready}
            onClick={() => setSettingsOpen(true)}
          >
            <SlidersHorizontal size={17} /> Council settings
          </button>
          <div className="account-row">
            <span className="avatar">{user.email[0].toUpperCase()}</span>
            <span>
              <strong>Your workspace</strong>
              <small>{user.email}</small>
            </span>
            <button
              className="icon-button"
              aria-label="Sign out"
              onClick={() => {
                void request("/auth/logout", { method: "POST" }).catch(
                  () => undefined,
                );
                logout();
              }}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-only"
              aria-label="Open navigation"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={20} />
            </button>
            <span className="topbar-label">
              {conversation?.title || "A space to think"}
            </span>
          </div>
          <div>
            <span className="private-badge">
              <span /> Private workspace
            </span>
            {conversation?.messages.length ? (
              <button
                className="icon-button"
                aria-label="Export conversation"
                onClick={() =>
                  void download(conversation.id).catch(() =>
                    setError("Export failed. Please try again."),
                  )
                }
              >
                <Download size={18} />
              </button>
            ) : null}
          </div>
        </header>
        <div
          className={`chat-scroll ${empty ? "is-empty" : ""}`}
          ref={scrollRef}
          onScroll={() => {
            const el = scrollRef.current;
            if (el)
              nearEnd.current =
                el.scrollHeight - el.scrollTop - el.clientHeight < 160;
          }}
        >
          <div className="chat-content">
            {empty ? (
              <section className="welcome">
                <div className="welcome-symbol" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
                <span className="eyebrow">A few good perspectives</span>
                <h1>What’s on your mind?</h1>
                <p>
                  Bring a question. Let different minds explore it.
                  <br />
                  Leave with a little more clarity.
                </p>
                <div className="suggestions">
                  {suggestions.map((s) => (
                    <button
                      key={s.label}
                      onClick={() => {
                        setInput(s.prompt);
                        inputRef.current?.focus();
                      }}
                    >
                      <s.icon size={20} />
                      <strong>{s.label}</strong>
                      <span>{s.text}</span>
                      <ArrowUpRight className="suggestion-arrow" size={16} />
                    </button>
                  ))}
                </div>
              </section>
            ) : (
              <>
                {conversation?.messages.map((message) => (
                  <article
                    className={`message ${message.role}`}
                    key={message.id}
                  >
                    {message.role === "user" ? (
                      <>
                        <div className="message-label">
                          <span className="mini-avatar">
                            {user.email[0].toUpperCase()}
                          </span>
                          You
                        </div>
                        <div className="user-content">{message.content}</div>
                      </>
                    ) : (
                      <>
                        <div className="message-label">
                          <span className="convene-avatar">c.</span>Convene{" "}
                          <span className="answer-state">
                            <Check size={12} /> Saved
                          </span>
                        </div>
                        <Suspense fallback={<p>Loading answer…</p>}>
                          <ResultView
                            result={
                              message.result || { content: message.content }
                            }
                            runId={
                              (
                                message.result as
                                  (Result & { run_id?: string }) | null
                              )?.run_id
                            }
                          />
                        </Suspense>
                      </>
                    )}
                  </article>
                ))}
                {runId && (
                  <article className="message assistant">
                    <div className="message-label">
                      <span className="convene-avatar">c.</span>Convene
                    </div>
                    <div
                      className="run-progress"
                      role="status"
                      aria-live="polite"
                    >
                      <LoaderCircle size={17} className="spin" />
                      <span>{run.progress}</span>
                    </div>
                    {run.result.content ? (
                      <Suspense fallback={<p>Loading answer…</p>}>
                        <ResultView result={run.result} />
                      </Suspense>
                    ) : (
                      <div className="thinking-lines" aria-hidden="true">
                        <i />
                        <i />
                        <i />
                      </div>
                    )}
                  </article>
                )}
              </>
            )}
            <div ref={endRef} />
          </div>
        </div>
        <div className="composer-area">
          <div className="composer-width">
            {error && (
              <div className="error-banner" role="alert">
                <span>{error}</span>
                <button
                  className="icon-button"
                  aria-label="Dismiss error"
                  onClick={() => setError("")}
                >
                  <X size={16} />
                </button>
              </div>
            )}
            {notice && <div className="notice">{notice}</div>}
            <form className="composer" onSubmit={send}>
              {documents.length > 0 && (
                <div className="attachments">
                  {documents.map((d, i) => (
                    <span key={i}>
                      <Paperclip size={13} />
                      {d.name}
                      <button
                        type="button"
                        className="icon-button"
                        aria-label={`Remove ${d.name}`}
                        onClick={() =>
                          setDocuments((prev) => prev.filter((_, n) => n !== i))
                        }
                      >
                        <X size={13} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <label className="sr-only" htmlFor="question">
                Your question
              </label>
              <textarea
                id="question"
                ref={inputRef}
                placeholder="Ask anything, or bring an idea to the table…"
                value={input}
                maxLength={12000}
                rows={2}
                onChange={(e) => {
                  setInput(e.target.value);
                  activeRequestKey.current = null;
                }}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    e.currentTarget.form?.requestSubmit();
                  }
                }}
              />
              <div className="composer-toolbar">
                <div>
                  <input
                    ref={fileRef}
                    type="file"
                    hidden
                    multiple
                    accept=".txt,.md,.pdf,.docx,.csv,.json,.py,.js,.ts"
                    onChange={(e) => void upload(e.target.files)}
                  />
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="Attach documents"
                    title="Attach up to 3 documents"
                    disabled={uploading || !!runId || submitting}
                    onClick={() => fileRef.current?.click()}
                  >
                    {uploading ? (
                      <LoaderCircle className="spin" size={18} />
                    ) : (
                      <Paperclip size={18} />
                    )}
                  </button>
                  <button
                    type="button"
                    className={`tool-chip ${settings.web_search_enabled ? "enabled" : ""}`}
                    disabled={!ready}
                    aria-pressed={settings.web_search_enabled}
                    title="Search the web for current information and sources. Sends your question to Tavily."
                    onClick={() =>
                      changeSettings({
                        ...settings,
                        web_search_enabled: !settings.web_search_enabled,
                      })
                    }
                  >
                    <Globe2 size={15} /> Web search
                  </button>
                  <label className="sr-only" htmlFor="mode">
                    Answer approach
                  </label>
                  <select
                    id="mode"
                    disabled={!ready}
                    className="mode-select"
                    value={settings.mode}
                    onChange={(e) =>
                      changeSettings({
                        ...settings,
                        mode: e.target.value as Settings["mode"],
                      })
                    }
                  >
                    <option value="auto">Auto</option>
                    <option value="fast">Quick</option>
                    <option value="council">Council</option>
                  </select>
                </div>
                {runId ? (
                  <button
                    type="button"
                    className="send-button stop"
                    aria-label="Stop answer"
                    onClick={() => void stop()}
                  >
                    <Square size={16} />
                  </button>
                ) : (
                  <button
                    type="submit"
                    className="send-button"
                    aria-label="Send question"
                    disabled={
                      !input.trim() || !ready || submitting || uploading
                    }
                  >
                    {submitting ? (
                      <LoaderCircle className="spin" size={19} />
                    ) : (
                      <ArrowUp size={20} />
                    )}
                  </button>
                )}
              </div>
            </form>
            <p className="composer-caption">
              {runId
                ? "You can leave this page. Your progress is saved."
                : "Multiple perspectives help. Check the evidence for important decisions."}
              <span>Shift + Enter for a new line</span>
            </p>
          </div>
        </div>
      </main>
      <SettingsPanel
        open={settingsOpen}
        close={() => setSettingsOpen(false)}
        value={settings}
        change={changeSettings}
        models={models}
      />
    </div>
  );
}
