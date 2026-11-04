"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { z } from "zod";
import { api, errorMessage, isActive } from "./api";
import type { Snapshot, StreamEvent } from "./types";

const eventEnvelope = z.object({
  seq: z.number().int(),
  type: z.string(),
  data: z.record(z.string(), z.unknown()),
  occurred_at: z.string(),
});

export function applyEvent(snapshot: Snapshot, event: StreamEvent): Snapshot {
  if (event.seq <= snapshot.cursor) return snapshot;
  const run = snapshot.run;
  if (!run) return snapshot;
  const data = event.data;
  let nextRun = run;
  let messages = snapshot.messages;
  const updateAssistant = (update: Partial<Snapshot["messages"][number]>) => {
    messages = messages.map((message) =>
      message.run_id === run.id && message.role === "assistant"
        ? { ...message, ...update }
        : message,
    );
  };
  if (event.type === "text.delta") {
    messages = messages.map((message) =>
      message.run_id === run.id && message.role === "assistant"
        ? { ...message, text: message.text + (data.delta ?? "") }
        : message,
    );
    nextRun = { ...run, first_text_at: run.first_text_at || event.occurred_at };
  } else if (event.type === "text.replace")
    updateAssistant({ text: data.text ?? "" });
  else if (event.type === "run.started")
    nextRun = { ...run, status: "RUNNING", started_at: event.occurred_at };
  else if (event.type === "plan.ready")
    nextRun = { ...run, mode: data.mode ?? run.mode };
  else if (event.type === "answer.started")
    updateAssistant({ citations: data.citations ?? [] });
  else if (event.type === "visualizations.ready")
    updateAssistant({ blocks: data.blocks ?? [] });
  else if (event.type === "run.completed") {
    nextRun = {
      ...run,
      status: "COMPLETED",
      metrics: data.metrics ?? {},
      finished_at: event.occurred_at,
    };
    updateAssistant({
      status: "COMPLETED",
      actions: data.actions ?? [],
      citations: data.citations ?? [],
      blocks: data.blocks ?? [],
    });
  } else if (event.type === "run.ended") {
    const status =
      data.status === "CANCELLED"
        ? "CANCELLED"
        : data.status === "INTERRUPTED"
          ? "INTERRUPTED"
          : "FAILED";
    nextRun = {
      ...run,
      status,
      error: data.error ?? null,
      finished_at: event.occurred_at,
    };
    updateAssistant({ status });
  }
  return {
    ...snapshot,
    messages,
    run: nextRun,
    cursor: event.seq,
    events: [...snapshot.events, event],
  };
}

export function useConversation(
  conversationId: string | null,
  active: boolean,
) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState<
    "connecting" | "live" | "reconnecting" | "saved"
  >("saved");
  const [revision, setRevision] = useState(0);
  const cursor = useRef(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    if (!conversationId || !active) return;
    let disposed = false;
    let source: EventSource | undefined;
    const controller = new AbortController();
    async function open() {
      try {
        const next = await api<Snapshot>(`/conversations/${conversationId}`, {
          signal: controller.signal,
        });
        if (disposed) return;
        setSnapshot(next);
        setError("");
        cursor.current = next.cursor;
        if (!isActive(next.run?.status) || !next.run) {
          setConnection("saved");
          return;
        }
        setConnection("connecting");
        source = new EventSource(
          `/api/v1/runs/${next.run.id}/events?after=${next.cursor}`,
        );
        source.onopen = () => {
          if (!disposed) setConnection("live");
        };
        source.onerror = () => {
          if (!disposed) setConnection("reconnecting");
        };
        source.addEventListener("update", (raw: MessageEvent<string>) => {
          const parsed = eventEnvelope.safeParse(JSON.parse(raw.data));
          if (!parsed.success || disposed || parsed.data.seq <= cursor.current)
            return;
          const event = parsed.data as StreamEvent;
          cursor.current = event.seq;
          setSnapshot((previous) =>
            previous?.conversation.id === conversationId
              ? applyEvent(previous, event)
              : previous,
          );
          if (event.type === "provider.finished") {
            void api<Snapshot>(`/conversations/${conversationId}`, {
              signal: controller.signal,
            })
              .then((reconciled) => {
                if (disposed) return;
                setSnapshot((previous) =>
                  !previous || reconciled.cursor >= previous.cursor
                    ? reconciled
                    : previous,
                );
                cursor.current = Math.max(cursor.current, reconciled.cursor);
              })
              .catch(() => {});
          }
        });
        source.addEventListener("caught-up", async () => {
          source?.close();
          if (disposed) return;
          setConnection("saved");
          const final = await api<Snapshot>(
            `/conversations/${conversationId}`,
            { signal: controller.signal },
          );
          if (!disposed) setSnapshot(final);
        });
      } catch (error) {
        if (!disposed) setError(errorMessage(error));
      }
    }
    void open();
    return () => {
      disposed = true;
      controller.abort();
      source?.close();
    };
  }, [conversationId, active, revision]);
  return {
    snapshot: snapshot?.conversation.id === conversationId ? snapshot : null,
    error,
    connection,
    refresh,
  };
}
