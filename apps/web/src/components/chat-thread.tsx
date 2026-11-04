"use client";

import dynamic from "next/dynamic";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAuiState,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BarChart3,
  Check,
  Copy,
  FileSearch,
  FileText,
  Paperclip,
  RotateCcw,
  Square,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { isActive } from "@/lib/api";
import type {
  Action,
  Bot,
  Citation,
  Message,
  Run,
  Session,
  Source,
} from "@/lib/types";
import { Badge, Button, IconButton, Menu, MenuItem, StatusBadge } from "./ui";

const Visualization = dynamic(
  () => import("./visualization").then((module) => module.Visualization),
  {
    ssr: false,
    loading: () => (
      <div className="visual-loading">Opening the visualization…</div>
    ),
  },
);

type ThreadContextValue = {
  messages: Map<string, Message>;
  run: Run | null;
  onSource: (citation: Citation) => void;
  onAction: (action: Action, message: Message) => void;
  onRetry: (question: string) => void;
  running: boolean;
};
const ThreadContext = createContext<ThreadContextValue | null>(null);
const convertMessage = (message: Message): ThreadMessageLike => ({
  id: message.id,
  role: message.role,
  content: [{ type: "text", text: message.text }],
  createdAt: new Date(message.created_at),
  status:
    message.role === "assistant"
      ? message.status === "RUNNING"
        ? { type: "running" }
        : message.status === "FAILED" || message.status === "INTERRUPTED"
          ? { type: "incomplete", reason: "error" }
          : message.status === "CANCELLED"
            ? { type: "incomplete", reason: "cancelled" }
            : { type: "complete", reason: "stop" }
      : undefined,
  metadata: { runId: message.run_id },
});

export function ChatThread({
  bot,
  session,
  messages,
  run,
  sending,
  attachments,
  onSend,
  onCancel,
  onSource,
  onAttach,
  onRemoveAttachment,
  onOpenAttachment,
  onAction,
}: {
  bot: Bot;
  session: Session;
  messages: Message[];
  run: Run | null;
  sending: boolean;
  attachments: Source[];
  onSend: (text: string, action?: Pick<Action, "id">) => Promise<void>;
  onCancel: () => Promise<void>;
  onSource: (citation: Citation) => void;
  onAttach: () => void;
  onRemoveAttachment: (source: Source) => void;
  onOpenAttachment: (source: Source) => void;
  onAction: (action: Action, message: Message) => void;
}) {
  const running = isActive(run?.status) || sending;
  const onNew = useCallback(
    async (message: AppendMessage) => {
      const text = message.content
        .filter((part) => part.type === "text")
        .map((part) => (part.type === "text" ? part.text : ""))
        .join("\n");
      if (text.trim()) await onSend(text);
    },
    [onSend],
  );
  const runtime = useExternalStoreRuntime({
    messages,
    convertMessage,
    isRunning: running,
    onNew,
    onCancel,
    activeRunId: run?.id,
  });
  const context = useMemo<ThreadContextValue>(
    () => ({
      messages: new Map(messages.map((message) => [message.id, message])),
      run,
      onSource,
      onAction,
      running,
      onRetry: (question) => {
        void onSend(
          question,
          run?.origin_action_id ? { id: run.origin_action_id } : undefined,
        );
      },
    }),
    [messages, run, onSource, onAction, running, onSend],
  );
  const pendingAttachments = attachments.some(
    (source) => !["READY", "READY_LEXICAL"].includes(source.status),
  );
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadContext.Provider value={context}>
        <ThreadPrimitive.Root className="chat-thread">
          <ThreadPrimitive.Viewport
            className="thread-viewport"
            autoScroll={messages.length > 0}
          >
            <div className="thread-content">
              <ThreadPrimitive.Empty>
                <Welcome
                  bot={bot}
                  onSend={(text) => {
                    void onSend(text);
                  }}
                />
              </ThreadPrimitive.Empty>
              <ThreadPrimitive.Messages
                components={{ UserMessage, AssistantMessage }}
              />
            </div>
            <ThreadPrimitive.ScrollToBottom
              className="scroll-to-bottom"
              aria-label="Scroll to latest message"
            >
              <ArrowDown size={16} />
            </ThreadPrimitive.ScrollToBottom>
          </ThreadPrimitive.Viewport>
          <div className="composer-wrap">
            {!!attachments.length && (
              <section aria-label="Conversation attachments">
                <span className="attachment-tray-label">
                  Conversation attachments
                </span>
                <div className="attachment-tray">
                  {attachments.map((source) => (
                    <div key={source.id} className="attachment-chip">
                      <button onClick={() => onOpenAttachment(source)}>
                        <FileText size={14} />
                        <span>{source.name}</span>
                        <StatusBadge status={source.status} />
                      </button>
                      <IconButton
                        label={`Remove ${source.name} from this conversation`}
                        onClick={() => onRemoveAttachment(source)}
                      >
                        <X size={13} />
                      </IconButton>
                    </div>
                  ))}
                </div>
              </section>
            )}
            <ComposerPrimitive.Root className="composer">
              <ComposerPrimitive.Input
                className="composer-input"
                aria-label={`Message ${bot.name}`}
                placeholder="Ask a question, explore a pattern, follow the evidence…"
                rows={1}
                submitMode="enter"
                addAttachmentOnPaste={false}
                maxLength={6000}
              />
              <div className="composer-bottom">
                <div className="inline-controls">
                  <IconButton
                    label="Attach a document or image"
                    onClick={onAttach}
                    disabled={running}
                  >
                    <Paperclip size={19} />
                  </IconButton>
                  <span className="composer-model">
                    <span className="live-dot" />
                    {session.capabilities.chat?.available
                      ? session.capabilities.chat.model.split("/").at(-1)
                      : "Evidence & analytics"}
                  </span>
                </div>
                {running ? (
                  <ComposerPrimitive.Cancel asChild>
                    <Button className="stop-button">
                      <Square size={13} fill="currentColor" />
                      Stop
                    </Button>
                  </ComposerPrimitive.Cancel>
                ) : (
                  <ComposerPrimitive.Send asChild>
                    <button
                      className="send-button"
                      aria-label="Send message"
                      disabled={pendingAttachments}
                    >
                      <ArrowUp size={19} />
                    </button>
                  </ComposerPrimitive.Send>
                )}
              </div>
            </ComposerPrimitive.Root>
            <p className="composer-note">
              {pendingAttachments
                ? "Review and approve the attached source before sending."
                : bot.is_seed
                  ? "Synthetic data · August–October 2026 · Check important answers against their sources."
                  : "Answers use this chatbot’s documents. Open citations to check the evidence."}
            </p>
            {(session.capabilities.embedding?.available ||
              session.capabilities.chat?.available) && (
              <p className="remote-disclosure">
                Questions and selected evidence may be sent to configured AI
                providers. Do not enter confidential or personal data.
              </p>
            )}
          </div>
        </ThreadPrimitive.Root>
      </ThreadContext.Provider>
    </AssistantRuntimeProvider>
  );
}

function Welcome({
  bot,
  onSend,
}: {
  bot: Bot;
  onSend: (question: string) => void;
}) {
  const questions = bot.is_seed
    ? [
        {
          icon: BarChart3,
          title: "Spot the trend",
          detail: "How did failure rates change over the last three months?",
          question:
            "Show the transaction failure rate trend for the last three months.",
        },
        {
          icon: FileSearch,
          title: "Investigate a change",
          detail: "Which channel drove October’s increase?",
          question:
            "Which payment channel contributed most to the October failure increase? Compare failure rates by channel.",
        },
        {
          icon: FileText,
          title: "Ask the documents",
          detail: "What should we do when a gateway times out?",
          question:
            "According to the incident SOP, what is the response to a gateway timeout? Show a process diagram.",
        },
      ]
    : [
        {
          icon: FileSearch,
          title: "Explore the evidence",
          detail: "What information is available in this chatbot?",
          question:
            "Summarize the main topics covered by the available documents and cite the sources.",
        },
        {
          icon: BarChart3,
          title: "Ask about your data",
          detail: "Compare a metric across categories or time.",
          question:
            "Show a monthly count of transactions in the available dataset.",
        },
      ];
  return (
    <div className="welcome">
      <div className="welcome-topline">
        <span className="welcome-mark">
          <span />
          <span />
          <span />
        </span>
        <Badge tone="green">A LITTLE MORE VISIBLE</Badge>
      </div>
      <h1>
        Good questions deserve
        <br />
        <span>visible workings.</span>
      </h1>
      <p>
        Ask {bot.name} about its documents and data.
        <br className="desktop-break" /> Follow the evidence, from first
        retrieval to final answer.
      </p>
      <div className="welcome-prompts">
        {questions.map((item) => (
          <button key={item.title} onClick={() => onSend(item.question)}>
            <item.icon size={19} />
            <div>
              <strong>{item.title}</strong>
              <span>{item.detail}</span>
            </div>
            <ArrowRight size={15} />
          </button>
        ))}
      </div>
      <div className="welcome-bottom">
        <span className="live-dot" />
        <span>{bot.source_count} sources connected</span>
        <span>·</span>
        <span>
          {bot.is_seed
            ? "Synthetic NTI operations corpus"
            : "Isolated knowledge collection"}
        </span>
      </div>
    </div>
  );
}

function useStoredMessage() {
  const context = useContext(ThreadContext);
  const id = useAuiState((state) => state.message.id);
  if (!context)
    throw new Error("Message must be inside the conversation runtime.");
  return { context, message: context.messages.get(id) };
}
function UserMessage() {
  const { message } = useStoredMessage();
  if (!message) return null;
  return (
    <MessagePrimitive.Root className="user-message">
      <div className="message-avatar user-avatar">Y</div>
      <div>
        <span className="message-author">You</span>
        <p>{message.text}</p>
        {!!message.attachments.length && (
          <span className="muted small">
            <Paperclip size={12} /> {message.attachments.length} attached source
            {message.attachments.length > 1 ? "s" : ""}
          </span>
        )}
      </div>
    </MessagePrimitive.Root>
  );
}
function AssistantMessage() {
  const { context, message } = useStoredMessage();
  const [copied, setCopied] = useState(false);
  const [tableId, setTableId] = useState("");
  if (!message) return null;
  const latest = message.run_id === context.run?.id;
  const currentRun = latest ? context.run : null;
  const hasAnswerText = Boolean(message.text.trim());
  const text = message.text.replace(/\[((?:S|D)\d+)\]/g, "[$1](#citation-$1)");
  function doAction(action: Action) {
    if (action.kind === "table") {
      setTableId(action.analysis_id ?? "");
      return;
    }
    if (message) context.onAction(action, message);
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(message?.text ?? "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }
  return (
    <MessagePrimitive.Root className="assistant-message">
      <div className="message-avatar assistant-avatar">
        <span className="brand-bars">
          <i />
          <i />
          <i />
        </span>
      </div>
      <div className="assistant-body">
        <div className="message-byline">
          <span className="message-author">Tampak</span>
          {currentRun?.mode === "EVIDENCE" && (
            <Badge tone="amber">Evidence mode</Badge>
          )}
          {message.status === "RUNNING" && (
            <span className="thinking-indicator">
              <span />
              <span />
              <span />
              {currentRun?.mode === "EVIDENCE"
                ? "Reading the evidence"
                : "Working with your sources"}
            </span>
          )}
        </div>
        {hasAnswerText && (
          <div className="markdown">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ href, children }) => {
                  if (href?.startsWith("#citation-")) {
                    const citation = message.citations.find(
                      (citation) => citation.id === href.slice(10),
                    );
                    return citation ? (
                      <button
                        className="inline-citation"
                        title={`Open ${citation.name}`}
                        onClick={() => context.onSource(citation)}
                      >
                        {children}
                      </button>
                    ) : (
                      <span className="missing-citation">{children}</span>
                    );
                  }
                  return href?.startsWith("https://") ? (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ) : (
                    <span>{children}</span>
                  );
                },
              }}
            >
              {text}
            </ReactMarkdown>
          </div>
        )}
        {!hasAnswerText && message.status === "RUNNING" && (
          <div className="answer-skeleton">
            <span />
            <span />
            <span />
          </div>
        )}
        {!hasAnswerText &&
          message.status !== "RUNNING" &&
          !message.blocks.length &&
          !currentRun?.error && (
            <div className="notice" role="status">
              The model returned no answer text. Retry as a new run or review
              its output and reasoning settings in Admin.
            </div>
          )}
        {message.blocks.map((block, index) => (
          <Visualization
            key={`${message.id}-${index}`}
            block={block}
            showTable={block.type === "chart" && tableId === block.analysis_id}
          />
        ))}
        {!!message.citations.length && (
          <div className="source-chips" aria-label="Answer sources">
            {message.citations.map((citation) => (
              <button
                key={citation.id}
                onClick={() => context.onSource(citation)}
                title={citation.name}
              >
                <span>{citation.id}</span>
                <FileText size={12} />
                <strong>{citation.name.replaceAll("_", " ")}</strong>
                <small>
                  {citation.kind === "dataset"
                    ? "data"
                    : citation.name.endsWith(".docx") ||
                        citation.name.endsWith(".md")
                      ? "section"
                      : `p. ${citation.locators[0]?.page ?? "—"}`}
                </small>
              </button>
            ))}
          </div>
        )}
        {message.status !== "RUNNING" && (
          <div className="message-utilities">
            <IconButton
              label={copied ? "Answer copied" : "Copy answer"}
              onClick={copy}
              disabled={!hasAnswerText}
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </IconButton>
            <span className="muted small">
              {message.status === "COMPLETED"
                ? "Check the source behind each claim"
                : message.status.toLowerCase()}
            </span>
            {(["FAILED", "INTERRUPTED", "CANCELLED"].includes(message.status) ||
              (!hasAnswerText && !message.blocks.length)) &&
              currentRun && (
                <Button
                  variant="ghost"
                  disabled={context.running}
                  onClick={() => context.onRetry(currentRun.question)}
                >
                  <RotateCcw size={13} />
                  Retry as a new run
                </Button>
              )}
          </div>
        )}
        {currentRun?.error && (
          <div className="run-error" role="alert">
            <strong>
              {currentRun.status === "CANCELLED"
                ? "Answer stopped"
                : "This run could not finish"}
            </strong>
            <p>{currentRun.error.message}</p>
          </div>
        )}
        {!!message.actions.length && (
          <div className="suggested-actions">
            <span className="eyebrow">KEEP EXPLORING</span>
            <div>
              {message.actions.slice(0, 3).map((action) => (
                <Button
                  key={action.id}
                  disabled={context.running && action.kind === "question"}
                  onClick={() => doAction(action)}
                >
                  {action.label}
                  <ArrowUp size={12} className="rotate-45" />
                </Button>
              ))}
              {message.actions.length > 3 && (
                <Menu label="More actions">
                  {message.actions.slice(3).map((action) => (
                    <MenuItem
                      key={action.id}
                      disabled={context.running && action.kind === "question"}
                      onSelect={() => doAction(action)}
                    >
                      {action.label}
                    </MenuItem>
                  ))}
                </Menu>
              )}
            </div>
          </div>
        )}
      </div>
    </MessagePrimitive.Root>
  );
}
