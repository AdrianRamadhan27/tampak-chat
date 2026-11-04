"use client";

import { useState } from "react";
import {
  ArrowUpRight,
  Bot as BotIcon,
  FileText,
  LockKeyhole,
  Plus,
  Settings2,
  Timer,
  Trash2,
} from "lucide-react";
import { api, errorMessage, post } from "@/lib/api";
import type { Bot, Session } from "@/lib/types";
import { Badge, Button, Dialog, ErrorBanner, Menu, MenuItem } from "./ui";

export function BotLibrary({
  bots,
  session,
  onSelect,
  onChanged,
}: {
  bots: Bot[];
  session: Session;
  onSelect: (bot: Bot) => void;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState<Bot | "new" | null>(null);
  const [deleting, setDeleting] = useState<Bot | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function remove() {
    if (!deleting) return;
    setBusy(true);
    try {
      await api(`/bots/${deleting.id}`, { method: "DELETE" });
      setDeleting(null);
      onChanged();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR WORKSPACE</span>
          <h1>A chatbot for every corpus.</h1>
          <p>
            Start with NTI Operations, or build a temporary assistant around
            your own documents.
          </p>
        </div>
        <Button variant="primary" onClick={() => setEditing("new")}>
          <Plus size={16} />
          Create chatbot
        </Button>
      </div>
      {error && <ErrorBanner message={error} dismiss={() => setError("")} />}
      <div className="bot-grid">
        {bots.map((bot, index) => (
          <article key={bot.id} className="bot-card">
            <div className="bot-card-top">
              <div className={`bot-avatar avatar-${index % 3}`}>
                <BotIcon size={26} />
              </div>
              {bot.is_seed ? (
                <Badge tone="green">Technical test · seeded</Badge>
              ) : (
                <Badge>
                  <Timer size={11} />
                  Temporary
                </Badge>
              )}
              {bot.can_edit && (
                <Menu
                  label={`Manage ${bot.name}`}
                  trigger={<Settings2 size={17} />}
                >
                  <MenuItem onSelect={() => setEditing(bot)}>
                    Edit chatbot
                  </MenuItem>
                  {!bot.is_seed && (
                    <MenuItem danger onSelect={() => setDeleting(bot)}>
                      <Trash2 size={14} />
                      Delete chatbot
                    </MenuItem>
                  )}
                </Menu>
              )}
            </div>
            <h2>{bot.name}</h2>
            <p>
              {bot.description ||
                "A private assistant for your documents and data."}
            </p>
            <div className="bot-card-meta">
              <span>
                <FileText size={14} />
                {bot.source_count} knowledge sources
              </span>
              <span>
                {bot.is_published ? (
                  "Public corpus · private chats"
                ) : (
                  <>
                    <LockKeyhole size={12} />
                    Private to your session
                  </>
                )}
              </span>
            </div>
            <Button
              onClick={() => onSelect(bot)}
              variant={bot.is_seed ? "primary" : "secondary"}
            >
              Open chatbot
              <ArrowUpRight size={16} />
            </Button>
          </article>
        ))}
        <button
          className="bot-card create-card"
          onClick={() => setEditing("new")}
        >
          <div className="empty-icon">
            <Plus size={24} />
          </div>
          <h2>Bring your own knowledge</h2>
          <p>Upload documents, choose a parser, and watch retrieval work.</p>
          <span className="text-link">
            Create a chatbot <ArrowUpRight size={14} />
          </span>
        </button>
      </div>
      {session.kind === "GUEST" && (
        <div className="workspace-note">
          <Timer size={19} />
          <div>
            <strong>A space to experiment</strong>
            <p>
              Your demo bots and conversations are private to this browser
              session and expire after 24 hours. You can create up to three bots
              and upload 50 MB in total.
            </p>
          </div>
        </div>
      )}
      <Dialog
        open={!!editing}
        onOpenChange={(open) => {
          if (!open) setEditing(null);
        }}
        title={editing === "new" ? "Create a chatbot" : "Edit chatbot"}
        description="Give this assistant a purpose and its own knowledge collection."
      >
        {editing && (
          <BotForm
            key={editing === "new" ? "new" : editing.id}
            bot={editing === "new" ? undefined : editing}
            admin={session.kind === "ADMIN"}
            onSave={(bot) => {
              setEditing(null);
              onChanged();
              if (editing === "new") onSelect(bot);
            }}
          />
        )}
      </Dialog>
      <Dialog
        open={!!deleting}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title="Delete this chatbot?"
        description="It will become unavailable, and any active answers will stop."
      >
        <div className="dialog-body">
          <p>
            {deleting?.name} and its knowledge collection will no longer be
            accessible.
          </p>
          <div className="dialog-footer">
            <Button onClick={() => setDeleting(null)}>Keep chatbot</Button>
            <Button variant="danger" busy={busy} onClick={remove}>
              Delete chatbot
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}

function BotForm({
  bot,
  admin,
  onSave,
}: {
  bot?: Bot;
  admin: boolean;
  onSave: (bot: Bot) => void;
}) {
  const [name, setName] = useState(bot?.name ?? "");
  const [description, setDescription] = useState(bot?.description ?? "");
  const [instruction, setInstruction] = useState(
    bot?.instruction ??
      "Use only available evidence, cite sources, and say when the documents do not support an answer.",
  );
  const [month, setMonth] = useState(bot?.reference_month ?? "2026-10");
  const [published, setPublished] = useState(bot?.is_published ?? false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = {
        name,
        description,
        instruction,
        reference_month: month,
        is_published: published,
      };
      if (bot) {
        await api(`/bots/${bot.id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
        onSave({ ...bot, ...body });
      } else onSave(await post<Bot>("/bots", body));
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="dialog-body form-stack" onSubmit={submit}>
      {error && <ErrorBanner message={error} />}
      <label>
        Chatbot name
        <input
          autoFocus
          required
          minLength={1}
          maxLength={100}
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="e.g. Product research assistant"
        />
      </label>
      <label>
        What is it for?
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          maxLength={500}
          placeholder="A short description of the questions it helps answer."
          rows={3}
        />
      </label>
      <details>
        <summary>Instructions & reference period</summary>
        <label>
          Assistant instructions
          <textarea
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            maxLength={4000}
            rows={4}
          />
        </label>
        <label>
          Reference month
          <input
            type="month"
            required
            value={month}
            onChange={(event) => setMonth(event.target.value)}
          />
        </label>
        <p className="muted small">
          Relative analytics dates use this month, so seeded examples remain
          reproducible.
        </p>
      </details>
      {admin ? (
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={published}
            onChange={(event) => setPublished(event.target.checked)}
          />
          Publish this corpus for demo visitors. Their conversations stay
          private.
        </label>
      ) : (
        <p className="muted small">
          Private temporary bot · expires in 24 hours.
        </p>
      )}
      <div className="dialog-footer">
        <Button variant="primary" type="submit" busy={busy}>
          {bot ? "Save changes" : "Create chatbot"}
        </Button>
      </div>
    </form>
  );
}
