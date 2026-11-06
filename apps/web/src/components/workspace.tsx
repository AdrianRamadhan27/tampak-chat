"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Bot as BotIcon,
  Check,
  ChevronDown,
  CircleHelp,
  FileText,
  FlaskConical,
  FolderOpen,
  Layers,
  LoaderCircle,
  LogOut,
  Menu as MenuIcon,
  MessageSquare,
  Moon,
  MoreHorizontal,
  Plus,
  Search,
  Settings2,
  Shield,
  Sun,
  Trash2,
  Upload,
  Workflow,
} from "lucide-react";
import {
  api,
  ApiError,
  errorMessage,
  isActive,
  post,
  setCsrf,
} from "@/lib/api";
import { useConversation } from "@/lib/use-conversation";
import type {
  Action,
  Bot,
  Citation,
  Conversation,
  Message,
  Session,
  Source,
  View,
} from "@/lib/types";
import { BotLibrary } from "./bots";
import { UsageSummary } from "./usage-summary";
import { ChatThread } from "./chat-thread";
import { Inspector } from "./inspector";
import { SourceViewer, type SourceTarget } from "./source-viewer";
import { UploadDialog, type Uploaded } from "./upload-dialog";
import {
  Badge,
  Button,
  Dialog,
  EmptyState,
  ErrorBanner,
  IconButton,
  Menu,
  MenuItem,
  StatusBadge,
  Toggle,
} from "./ui";

const Admin = dynamic(() => import("./admin"), {
  loading: () => (
    <div className="content-page muted">Opening model settings…</div>
  ),
});
const Login = dynamic(() => import("./login"));
const Evaluations = dynamic(() => import("./evaluations"));
const NAV = [
  { view: "chat", label: "Conversation", icon: MessageSquare },
  { view: "bots", label: "Chatbots", icon: Layers },
  { view: "sources", label: "Knowledge", icon: FolderOpen },
  { view: "activity", label: "Activity", icon: Activity },
  { view: "evaluations", label: "Evaluation", icon: FlaskConical },
] as const;

export function Workspace() {
  const [requiresLogin, setRequiresLogin] = useState(false);
  const [bootstrapAttempt, setBootstrapAttempt] = useState(0);
  const [session, setSession] = useState<Session | null>(null);
  const [bots, setBots] = useState<Bot[]>([]);
  const [botId, setBotId] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [view, setView] = useState<View>("chat");
  const [railOpen, setRailOpen] = useState(false);
  const [pipeline, setPipeline] = useState(true);
  const [metrics, setMetrics] = useState(true);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadConversation, setUploadConversation] = useState<
    string | undefined
  >();
  const [reprocess, setReprocess] = useState<{
    revision_id: string;
    name: string;
  }>();
  const [target, setTarget] = useState<SourceTarget | null>(null);
  const [sourceRevision, setSourceRevision] = useState(0);
  const [helpOpen, setHelpOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [deleting, setDeleting] = useState<Source | null>(null);
  const [deleteChatOpen, setDeleteChatOpen] = useState(false);
  const sendingRef = useRef(false);
  const sessionRef = useRef<Session | null>(null);
  const selectionRef = useRef({
    botId: "",
    conversationId: null as string | null,
    view: "chat" as View,
  });
  const bot = bots.find((bot) => bot.id === botId) ?? bots[0];
  const chat = useConversation(
    conversationId,
    view === "chat" || view === "activity",
  );
  const refreshChat = chat.refresh;
  const activeRun = chat.snapshot?.run;
  const changed = useCallback(
    () => setSourceRevision((value) => value + 1),
    [],
  );

  const refreshBots = useCallback(async () => {
    try {
      setBots(await api<Bot[]>("/bots"));
    } catch (error) {
      setError(errorMessage(error));
    }
  }, []);
  const sessionChanged = useCallback(async () => {
    const next = await api<Session>("/session");
    setCsrf(next.csrf);
    if (sessionRef.current?.id !== next.id) {
      setConversationId(null);
      setConversations([]);
      setSources([]);
      selectionRef.current.conversationId = null;
    }
    sessionRef.current = next;
    setSession(next);
    await refreshBots();
  }, [refreshBots]);

  useEffect(() => {
    let disposed = false;
    async function initialize() {
      try {
        let next: Session;
        try {
          next = await api<Session>("/session");
        } catch (error) {
          if (disposed) return;
          if (!(error instanceof ApiError) || error.status !== 401) throw error;
          const result = await post<{ csrf: string }>("/session/guest");
          setCsrf(result.csrf);
          next = await api<Session>("/session");
        }
        setCsrf(next.csrf);
        const bots = await api<Bot[]>("/bots");
        if (disposed) return;
        const params = new URLSearchParams(window.location.search);
        const savedBot =
          params.get("bot") || localStorage.getItem(`tampak:${next.id}:bot`);
        const selected = bots.find((bot) => bot.id === savedBot) ?? bots[0];
        const savedChat =
          params.get("chat") ||
          localStorage.getItem(`tampak:${next.id}:${selected?.id}:chat`);
        const savedView = params.get("view");
        const nextView: View = [
          "chat",
          "bots",
          "sources",
          "activity",
          "evaluations",
          "admin",
        ].includes(savedView ?? "")
          ? (savedView as View)
          : "chat";
        const dark = localStorage.getItem("tampak:theme") === "dark";
        setTheme(dark ? "dark" : "light");
        document.documentElement.dataset.theme = dark ? "dark" : "light";
        setPipeline(localStorage.getItem("tampak:pipeline") !== "false");
        setMetrics(localStorage.getItem("tampak:metrics") !== "false");
        sessionRef.current = next;
        setSession(next);
        setBots(bots);
        setBotId(selected?.id ?? "");
        setConversationId(savedChat);
        setView(nextView);
        selectionRef.current = {
          botId: selected?.id ?? "",
          conversationId: savedChat,
          view: nextView,
        };
      } catch (error) {
        if (!disposed) {
          if (error instanceof ApiError && error.code === "AUTH_REQUIRED") {
            setRequiresLogin(true);
          } else {
            setError(errorMessage(error));
          }
        }
      }
    }
    void initialize();
    return () => {
      disposed = true;
    };
  }, [bootstrapAttempt]);

  useEffect(() => {
    if (!session || !botId) return;
    let disposed = false;
    Promise.all([
      api<Conversation[]>(`/bots/${botId}/conversations`),
      api<Source[]>(
        `/bots/${botId}/sources${conversationId ? `?conversation_id=${conversationId}` : ""}`,
      ),
    ])
      .then(([conversations, sources]) => {
        if (!disposed) {
          setConversations(conversations);
          setSources(sources);
        }
      })
      .catch((error) => {
        if (!disposed) setError(errorMessage(error));
      });
    return () => {
      disposed = true;
    };
  }, [
    session,
    botId,
    conversationId,
    sourceRevision,
    chat.snapshot?.run?.status,
  ]);

  function remember(next: {
    botId: string;
    conversationId: string | null;
    view: View;
  }) {
    selectionRef.current = next;
    const params = new URLSearchParams();
    if (next.botId) params.set("bot", next.botId);
    if (next.conversationId) params.set("chat", next.conversationId);
    if (next.view !== "chat") params.set("view", next.view);
    window.history.replaceState(null, "", `/?${params}`);
    if (sessionRef.current) {
      localStorage.setItem(`tampak:${sessionRef.current.id}:bot`, next.botId);
      const key = `tampak:${sessionRef.current.id}:${next.botId}:chat`;
      if (next.conversationId) localStorage.setItem(key, next.conversationId);
      else localStorage.removeItem(key);
    }
  }
  function navigate(nextView: View) {
    setView(nextView);
    setRailOpen(false);
    remember({ ...selectionRef.current, view: nextView });
  }
  function selectBot(nextBot: Bot) {
    setBotId(nextBot.id);
    setConversationId(null);
    setSources([]);
    setView("chat");
    setRailOpen(false);
    setError("");
    remember({ botId: nextBot.id, conversationId: null, view: "chat" });
  }
  function selectConversation(conversation: Conversation) {
    setConversationId(conversation.id);
    setView("chat");
    setRailOpen(false);
    setError("");
    remember({
      botId: conversation.bot_id,
      conversationId: conversation.id,
      view: "chat",
    });
  }
  function newConversation() {
    setConversationId(null);
    setView("chat");
    setError("");
    setRailOpen(false);
    remember({ ...selectionRef.current, conversationId: null, view: "chat" });
  }

  const send = useCallback(
    async (question: string, action?: Pick<Action, "id">) => {
      const selection = selectionRef.current;
      if (!selection.botId || sendingRef.current) return;
      sendingRef.current = true;
      setSending(true);
      setError("");
      try {
        let id = selection.conversationId;
        if (!id) {
          const conversation = await post<Conversation>(
            `/bots/${selection.botId}/conversations`,
          );
          id = conversation.id;
          setConversationId(id);
          setConversations((previous) => [conversation, ...previous]);
          selectionRef.current = {
            ...selectionRef.current,
            conversationId: id,
          };
          const params = new URLSearchParams(window.location.search);
          params.set("chat", id);
          window.history.replaceState(null, "", `/?${params}`);
          if (sessionRef.current)
            localStorage.setItem(
              `tampak:${sessionRef.current.id}:${selection.botId}:chat`,
              id,
            );
        }
        await post(`/conversations/${id}/runs`, {
          question,
          request_key: crypto.randomUUID(),
          action_id: action?.id ?? null,
          attachments: sources
            .filter((source) => source.conversation_id === id && source.enabled)
            .map((source) => source.id),
        });
        refreshChat();
        changed();
      } catch (error) {
        setError(errorMessage(error));
      } finally {
        sendingRef.current = false;
        setSending(false);
      }
    },
    [sources, refreshChat, changed],
  );
  const cancel = useCallback(async () => {
    if (!activeRun) return;
    try {
      await post(`/runs/${activeRun.id}/cancel`);
    } catch (error) {
      setError(errorMessage(error));
    }
  }, [activeRun]);
  const openSource = useCallback(
    (citation: Citation) =>
      setTarget({ revision_id: citation.revision_id, citation }),
    [],
  );
  const act = useCallback(
    (action: Action, message: Message) => {
      if (action.kind === "source") {
        const citation = message.citations.find(
          (citation) => citation.id === action.citation_id,
        );
        if (citation) openSource(citation);
      } else if (action.kind === "question" && action.question)
        void send(action.question, action);
    },
    [send, openSource],
  );
  async function attach() {
    if (!bot) return;
    try {
      let id = conversationId;
      if (!id) {
        const conversation = await post<Conversation>(
          `/bots/${bot.id}/conversations`,
        );
        id = conversation.id;
        setConversationId(id);
        setConversations((previous) => [conversation, ...previous]);
        remember({ ...selectionRef.current, conversationId: id });
      }
      setUploadConversation(id);
      setReprocess(undefined);
      setUploadOpen(true);
    } catch (error) {
      setError(errorMessage(error));
    }
  }
  function uploaded(result: Uploaded) {
    changed();
    setTarget({ revision_id: result.revision_id, review: true });
  }
  async function toggleSource(source: Source, enabled: boolean) {
    try {
      await api(`/sources/${source.id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled, purpose: "knowledge-management" }),
      });
      changed();
    } catch (error) {
      setError(errorMessage(error));
    }
  }
  async function removeAttachment(source: Source) {
    if (!conversationId || source.conversation_id !== conversationId) return;
    try {
      await api(`/conversations/${conversationId}/attachments/${source.id}`, {
        method: "DELETE",
      });
      changed();
    } catch (error) {
      setError(errorMessage(error));
    }
  }
  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    localStorage.setItem("tampak:theme", next);
  }
  async function logout() {
    try {
      await post("/session/logout");
      // A full navigation clears cached conversation state after signing out.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/");
    } catch (error) {
      setError(errorMessage(error));
    }
  }
  const permanentSources = sources.filter((source) => !source.conversation_id);
  const activeKnowledge = permanentSources.filter(
    (source) => source.enabled && source.active_revision_id,
  );
  const attachments = sources.filter(
    (source) =>
      conversationId !== null &&
      source.conversation_id === conversationId &&
      source.enabled,
  );

  if (requiresLogin)
    return (
      <main>
        <Login
          purpose="workspace"
          onSessionChanged={async () => {
            setError("");
            setRequiresLogin(false);
            setBootstrapAttempt((attempt) => attempt + 1);
          }}
        />
      </main>
    );

  if (!session)
    return (
      <main className="boot-screen">
        <div className="brand-bars">
          <i />
          <i />
          <i />
        </div>
        <h1>Tampak-Chat</h1>
        {error ? (
          <>
            <ErrorBanner message={error} />
            <Button onClick={() => window.location.reload()}>
              Retry connection
            </Button>
          </>
        ) : (
          <p>
            <LoaderCircle size={15} className="spin" />
            Opening your workspace…
          </p>
        )}
      </main>
    );
  return (
    <div className="workspace">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {railOpen && (
        <button
          className="rail-scrim"
          aria-label="Close navigation"
          onClick={() => setRailOpen(false)}
        />
      )}
      <aside
        className={`sidebar ${railOpen ? "pinned-open" : ""}`}
        aria-label="Workspace navigation"
      >
        <button
          className="brand"
          aria-label="Toggle navigation"
          aria-expanded={railOpen}
          onClick={() => setRailOpen((value) => !value)}
        >
          <span className="brand-symbol">
            <span className="brand-bars">
              <i />
              <i />
              <i />
            </span>
          </span>
          <span className="rail-label">
            <strong>
              Tampak<span>-Chat</span>
            </strong>
            <small>THE VISIBLE WORKSPACE</small>
          </span>
        </button>
        <div className="sidebar-divider" />
        <nav>
          {NAV.filter(
            (item) => item.view !== "evaluations" || session.kind === "ADMIN",
          ).map((item) => (
            <button
              className={`nav-item ${view === item.view ? "active" : ""}`}
              key={item.view}
              onClick={() => navigate(item.view)}
              aria-label={item.label}
              aria-current={view === item.view ? "page" : undefined}
            >
              <item.icon size={20} />
              <span className="rail-label">{item.label}</span>
              {view === item.view && <span className="nav-active-dot" />}
            </button>
          ))}
        </nav>
        <div className="rail-history">
          <div className="section-heading">
            <span className="eyebrow">RECENT CONVERSATIONS</span>
            <IconButton label="New conversation" onClick={newConversation}>
              <Plus size={15} />
            </IconButton>
          </div>
          <label className="history-search">
            <Search size={13} />
            <input
              aria-label="Search conversations"
              placeholder="Find a conversation"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          {conversations
            .filter((conversation) =>
              conversation.title.toLowerCase().includes(search.toLowerCase()),
            )
            .slice(0, 8)
            .map((conversation) => (
              <button
                key={conversation.id}
                className={`history-item ${conversationId === conversation.id ? "selected" : ""}`}
                onClick={() => selectConversation(conversation)}
              >
                <MessageSquare size={13} />
                <span>{conversation.title}</span>
                {isActive(conversation.run_status) && (
                  <span className="live-dot active" />
                )}
              </button>
            ))}
          {!conversations.length && (
            <p className="muted small">
              Your first question starts a conversation.
            </p>
          )}
        </div>
        <div className="sidebar-bottom">
          {session.kind === "GUEST" && (
            <UsageSummary
              refreshKey={`${session.id}:${sourceRevision}:${bots.length}:${chat.snapshot?.run?.status ?? "idle"}`}
            />
          )}
          <button
            className="nav-item"
            aria-label={
              theme === "light"
                ? "Switch to dark theme"
                : "Switch to light theme"
            }
            onClick={toggleTheme}
          >
            {theme === "light" ? <Moon size={19} /> : <Sun size={19} />}
            <span className="rail-label">
              {theme === "light" ? "Dark theme" : "Light theme"}
            </span>
          </button>
          <button
            className={`nav-item ${view === "admin" ? "active" : ""}`}
            aria-label="Admin settings"
            onClick={() => navigate("admin")}
          >
            <Settings2 size={19} />
            <span className="rail-label">Admin settings</span>
          </button>
          <button
            className="nav-item"
            aria-label="About Tampak-Chat"
            onClick={() => setHelpOpen(true)}
          >
            <CircleHelp size={19} />
            <span className="rail-label">About this workspace</span>
          </button>
          <div className="sidebar-divider" />
          <div className="session-indicator">
            <span className="session-avatar">
              {session.kind === "ADMIN" ? "A" : "G"}
            </span>
            <div className="rail-label">
              <strong>
                {session.kind === "ADMIN" ? "Administrator" : "Guest workspace"}
              </strong>
              <small>
                {session.kind === "ADMIN"
                  ? "Persistent access"
                  : "Private · 24-hour demo"}
              </small>
            </div>
            {session.kind === "ADMIN" && (
              <span className="rail-label">
                <IconButton label="Sign out" onClick={logout}>
                  <LogOut size={15} />
                </IconButton>
              </span>
            )}
          </div>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="header-context">
            <IconButton
              label="Open navigation"
              onClick={() => setRailOpen((value) => !value)}
            >
              <MenuIcon size={19} />
            </IconButton>
            <span className="header-breadcrumb">
              Workspace<span>/</span>
            </span>
            <Menu
              label="Choose chatbot"
              align="start"
              trigger={
                <>
                  <span className="bot-mini">
                    <BotIcon size={16} />
                  </span>
                  <strong>{bot?.name ?? "Chatbots"}</strong>
                  <ChevronDown size={13} />
                </>
              }
            >
              {bots.map((item) => (
                <MenuItem key={item.id} onSelect={() => selectBot(item)}>
                  <BotIcon size={14} />
                  {item.name}
                  {item.id === botId && <Check size={13} />}
                </MenuItem>
              ))}
              <MenuItem onSelect={() => navigate("bots")}>
                <Plus size={14} />
                Manage chatbots
              </MenuItem>
            </Menu>
            <Badge tone="green">
              {bot?.is_seed ? "Synthetic corpus" : "Private demo"}
            </Badge>
          </div>
          <div className="header-controls">
            {view === "chat" || view === "activity" ? (
              <>
                <Toggle
                  checked={pipeline}
                  onChange={(value) => {
                    setPipeline(value);
                    localStorage.setItem("tampak:pipeline", String(value));
                  }}
                  icon={<Workflow size={15} />}
                >
                  Pipeline
                </Toggle>
                <Toggle
                  checked={metrics}
                  onChange={(value) => {
                    setMetrics(value);
                    localStorage.setItem("tampak:metrics", String(value));
                  }}
                  icon={<Activity size={15} />}
                >
                  Metrics
                </Toggle>
                <span className="header-separator" />
                <IconButton
                  label="Start a new conversation"
                  onClick={newConversation}
                >
                  <Plus size={19} />
                </IconButton>
              </>
            ) : (
              <Badge>{session.kind === "ADMIN" ? "Admin" : "Guest"}</Badge>
            )}
          </div>
        </header>
        {error && (
          <div className="global-error">
            <ErrorBanner message={error} dismiss={() => setError("")} />
          </div>
        )}
        <main id="main-content" className={`main-content view-${view}`}>
          {view === "chat" && bot && (
            <div className="chat-layout">
              <div className="chat-subheader">
                <div>
                  <span className="live-dot" />
                  <span>
                    {chat.snapshot?.conversation.title ?? "New conversation"}
                  </span>
                </div>
                <div className="inline-controls">
                  <button
                    className="text-link"
                    title={`${activeKnowledge.length} active knowledge sources; ${permanentSources.length} total. Manage them in Knowledge.`}
                    onClick={() => navigate("sources")}
                  >
                    <BookOpen size={13} />
                    {activeKnowledge.length} knowledge{" "}
                    {activeKnowledge.length === 1 ? "source" : "sources"}
                  </button>
                  <span className="subheader-divider" />
                  <span className="muted small">
                    {bot.reference_month} · {bot.timezone}
                  </span>
                  <Menu
                    label="Conversation actions"
                    trigger={<MoreHorizontal size={17} />}
                  >
                    <MenuItem
                      disabled={!chat.snapshot}
                      onSelect={() => {
                        if (!chat.snapshot) return;
                        const text = chat.snapshot.messages
                          .map(
                            (message) =>
                              `## ${message.role === "user" ? "You" : "Tampak"}\n\n${message.text}\n\n${message.citations.map((citation) => `${citation.id}: ${citation.name}, revision ${citation.revision_number ?? 1}, page/section ${citation.locators[0]?.page ?? 1}`).join("\n")}`,
                          )
                          .join("\n\n");
                        const url = URL.createObjectURL(
                          new Blob([text], { type: "text/markdown" }),
                        );
                        const link = document.createElement("a");
                        link.href = url;
                        link.download = "tampak-conversation.md";
                        link.click();
                        URL.revokeObjectURL(url);
                      }}
                    >
                      Export conversation
                    </MenuItem>
                    <MenuItem onSelect={newConversation}>
                      New conversation
                    </MenuItem>
                    <MenuItem
                      danger
                      disabled={!conversationId}
                      onSelect={() => setDeleteChatOpen(true)}
                    >
                      Delete conversation
                    </MenuItem>
                  </Menu>
                </div>
              </div>
              <div className="chat-body">
                <div className="chat-pane">
                  {chat.error && (
                    <div className="global-error">
                      <ErrorBanner message={chat.error} />
                      <Button variant="ghost" onClick={newConversation}>
                        Start a new conversation
                      </Button>
                    </div>
                  )}
                  <ChatThread
                    key={`${session.id}:${conversationId ?? "new"}`}
                    bot={bot}
                    session={session}
                    messages={chat.snapshot?.messages ?? []}
                    run={chat.snapshot?.run ?? null}
                    sending={sending}
                    attachments={attachments}
                    onSend={send}
                    onCancel={cancel}
                    onSource={openSource}
                    onAttach={() => {
                      void attach();
                    }}
                    onRemoveAttachment={(source) => {
                      void removeAttachment(source);
                    }}
                    onOpenAttachment={(source) =>
                      setTarget({
                        revision_id: source.latest_revision_id,
                        review: true,
                      })
                    }
                    onAction={act}
                  />
                </div>
                <Inspector
                  snapshot={chat.snapshot}
                  pipeline={pipeline}
                  metrics={metrics}
                  connection={chat.connection}
                  onSource={openSource}
                />
              </div>
            </div>
          )}
          {view === "bots" && (
            <BotLibrary
              bots={bots}
              session={session}
              onSelect={selectBot}
              onChanged={() => {
                void refreshBots();
              }}
            />
          )}
          {view === "sources" && bot && (
            <div className="content-page">
              <div className="page-heading">
                <div>
                  <span className="eyebrow">
                    {bot.name.toUpperCase()} / KNOWLEDGE
                  </span>
                  <h1>Good answers start here.</h1>
                  <p>
                    Review what this chatbot knows, how it was read, and which
                    revision is active.
                  </p>
                </div>
                <Button
                  variant="primary"
                  disabled={!bot.can_edit}
                  onClick={() => {
                    setReprocess(undefined);
                    setUploadConversation(undefined);
                    setUploadOpen(true);
                  }}
                >
                  <Upload size={16} />
                  Add knowledge
                </Button>
              </div>
              {!bot.can_edit && (
                <div className="notice">
                  <Shield size={18} />
                  <p>
                    This seeded corpus is managed by the administrator.{" "}
                    <button
                      className="text-link"
                      onClick={() => navigate("bots")}
                    >
                      Create your own chatbot
                    </button>{" "}
                    to upload permanent demo knowledge, or attach a file
                    privately inside a conversation.
                  </p>
                </div>
              )}
              {permanentSources.length ? (
                <div className="source-list">
                  {permanentSources.map((source) => (
                    <article
                      className={`source-list-row ${!source.enabled ? "source-disabled" : ""}`}
                      key={source.id}
                    >
                      <div className="file-kind-icon">
                        <FileText size={22} />
                      </div>
                      <button
                        className="source-row-main"
                        onClick={() =>
                          setTarget({
                            revision_id: source.latest_revision_id,
                            review: bot.can_edit,
                          })
                        }
                      >
                        <strong>{source.name}</strong>
                        <span>
                          {source.kind.toLowerCase()} · v
                          {source.revision_number} ·{" "}
                          {(source.size_bytes / 1024).toFixed(0)} KB ·{" "}
                          {source.page_count} pages / groups ·{" "}
                          {source.chunk_count} chunks
                          {source.processing_method
                            ? ` · ${source.processing_method}`
                            : ""}
                          {source.revision_created_at
                            ? ` · ${new Date(source.revision_created_at).toLocaleDateString()}`
                            : ""}
                        </span>
                        {source.active_revision_id &&
                          source.active_revision_id !==
                            source.latest_revision_id && (
                            <small>
                              Previous revision remains active while this
                              revision is reviewed.
                            </small>
                          )}
                      </button>
                      <div className="source-row-status">
                        <StatusBadge status={source.status} />
                        <span className="muted small">
                          {source.embedding_status === "READY"
                            ? "Vector index ready"
                            : source.embedding_status === "PENDING_CONFIG"
                              ? "Embedding key needed"
                              : source.embedding_status
                                  .toLowerCase()
                                  .replaceAll("_", " ")}
                        </span>
                      </div>
                      <Menu
                        label={`Manage ${source.name}`}
                        trigger={<MoreHorizontal size={19} />}
                      >
                        <MenuItem
                          onSelect={() =>
                            setTarget({
                              revision_id: source.latest_revision_id,
                              review: bot.can_edit,
                            })
                          }
                        >
                          Open extraction & review
                        </MenuItem>
                        <MenuItem
                          disabled={!bot.can_edit}
                          onSelect={() => {
                            setReprocess({
                              revision_id: source.latest_revision_id,
                              name: source.name,
                            });
                            setUploadConversation(undefined);
                            setUploadOpen(true);
                          }}
                        >
                          Reprocess with another method
                        </MenuItem>
                        <MenuItem
                          disabled={!bot.can_edit}
                          onSelect={() => {
                            void toggleSource(source, !source.enabled);
                          }}
                        >
                          {source.enabled
                            ? "Exclude from future answers"
                            : "Include in future answers"}
                        </MenuItem>
                        <MenuItem
                          danger
                          disabled={!bot.can_edit}
                          onSelect={() => setDeleting(source)}
                        >
                          <Trash2 size={13} />
                          Delete source
                        </MenuItem>
                      </Menu>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={<FolderOpen size={30} />}
                  title="A fresh knowledge collection"
                  action={
                    <Button
                      variant="primary"
                      disabled={!bot.can_edit}
                      onClick={() => {
                        setReprocess(undefined);
                        setUploadConversation(undefined);
                        setUploadOpen(true);
                      }}
                    >
                      Add your first source
                    </Button>
                  }
                >
                  Documents are extracted, reviewed, chunked and indexed before
                  they become available to this chatbot.
                </EmptyState>
              )}
              <div className="knowledge-explainer">
                <div>
                  <span>01</span>
                  <h3>Read it well</h3>
                  <p>
                    Choose native parsing, layout + OCR or a configured vision
                    model for each file.
                  </p>
                </div>
                <div>
                  <span>02</span>
                  <h3>Check the extraction</h3>
                  <p>
                    Preview text, tables, figures and quality warnings before a
                    revision goes live.
                  </p>
                </div>
                <div>
                  <span>03</span>
                  <h3>Keep the evidence</h3>
                  <p>
                    Every chunk keeps its source revision and page or section
                    anchors.
                  </p>
                </div>
              </div>
            </div>
          )}
          {view === "activity" && (
            <div className="content-page activity-page">
              <div className="page-heading">
                <div>
                  <span className="eyebrow">RUN ACTIVITY</span>
                  <h1>Nothing disappears behind a spinner.</h1>
                  <p>
                    Open an in-progress conversation to restore its current
                    state and resume the live stream.
                  </p>
                </div>
              </div>
              <div className="activity-layout">
                <div className="activity-conversations">
                  {conversations.map((conversation) => (
                    <button
                      key={conversation.id}
                      onClick={() => selectConversation(conversation)}
                    >
                      <MessageSquare size={17} />
                      <div>
                        <strong>{conversation.title}</strong>
                        <small>
                          {new Date(conversation.updated_at).toLocaleString()}
                        </small>
                      </div>
                      {conversation.run_status && (
                        <StatusBadge status={conversation.run_status} />
                      )}
                      <ArrowRight size={15} />
                    </button>
                  ))}
                  {!conversations.length && (
                    <EmptyState
                      icon={<Activity size={28} />}
                      title="Your first run starts with a question"
                    >
                      Each conversation keeps its answer, tool output and event
                      trail.
                    </EmptyState>
                  )}
                </div>
                <Inspector
                  snapshot={chat.snapshot}
                  pipeline={pipeline}
                  metrics={metrics}
                  connection={chat.connection}
                  onSource={openSource}
                />
              </div>
            </div>
          )}
          {view === "admin" && (
            <Admin session={session} onSessionChanged={sessionChanged} />
          )}
          {view === "evaluations" && bot && session.kind === "ADMIN" && (
            <Evaluations
              key={bot.id}
              bot={bot}
              sources={sources}
              onCitation={openSource}
            />
          )}
        </main>
      </div>
      <SourceViewer
        target={target}
        onClose={() => setTarget(null)}
        onChanged={changed}
        canEdit={!!bot?.can_edit || !!target?.review}
      />
      {uploadOpen && bot && (
        <UploadDialog
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          bot={bot}
          session={session}
          conversationId={uploadConversation}
          reprocess={reprocess}
          onUploaded={uploaded}
        />
      )}
      <Dialog
        open={helpOpen}
        onOpenChange={setHelpOpen}
        title="Tampak means visible."
        description="A chatbot workspace that lets you follow the evidence."
      >
        <div className="dialog-body about-content">
          <p>
            Ask a question, inspect the real retrieval and analysis steps, open
            a cited source, and see model usage without leaving the
            conversation.
          </p>
          <div className="about-features">
            <span>
              <Workflow size={20} />
              Observable RAG pipeline
            </span>
            <span>
              <FileText size={20} />
              Sources at the correct revision
            </span>
            <span>
              <Activity size={20} />
              Live latency, tokens and cost
            </span>
          </div>
          <h3>Your private demo</h3>
          <p>
            Temporary chatbots and conversations belong to this browser’s
            session. Guest data expires in 24 hours. The seeded NTI Operations
            corpus is fictional and available to every visitor.
          </p>
          <h3>Local-first, with configurable AI</h3>
          <p>
            Native extraction and dataset queries run locally. Embedding and
            configured chat/vision calls use external providers. The selected
            embedding model is Qwen3 Embedding 8B through OpenRouter. Share only
            documents you have permission to send to the configured providers.
          </p>
          <Button onClick={() => setHelpOpen(false)} variant="primary">
            Got it
          </Button>
        </div>
      </Dialog>
      <Dialog
        open={deleteChatOpen}
        onOpenChange={setDeleteChatOpen}
        title="Delete this conversation?"
        description="It will be removed from your history. An active answer will stop."
      >
        <div className="dialog-body">
          <p>{chat.snapshot?.conversation.title}</p>
          <div className="dialog-footer">
            <Button onClick={() => setDeleteChatOpen(false)}>
              Keep conversation
            </Button>
            <Button
              variant="danger"
              onClick={async () => {
                if (!conversationId) return;
                try {
                  await api(`/conversations/${conversationId}`, {
                    method: "DELETE",
                  });
                  setDeleteChatOpen(false);
                  newConversation();
                  changed();
                } catch (error) {
                  setError(errorMessage(error));
                }
              }}
            >
              Delete conversation
            </Button>
          </div>
        </div>
      </Dialog>
      <Dialog
        open={!!deleting}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title="Delete this source?"
        description="Future answers will stop using it. Earlier citations will show that it is unavailable."
      >
        <div className="dialog-body">
          <p>{deleting?.name}</p>
          <div className="dialog-footer">
            <Button onClick={() => setDeleting(null)}>Keep source</Button>
            <Button
              variant="danger"
              onClick={async () => {
                if (!deleting) return;
                try {
                  await api(`/sources/${deleting.id}`, { method: "DELETE" });
                  setDeleting(null);
                  changed();
                } catch (error) {
                  setError(errorMessage(error));
                }
              }}
            >
              Delete source
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
