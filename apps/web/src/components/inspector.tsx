"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Braces,
  Check,
  ChevronDown,
  Clock3,
  Coins,
  Database,
  FileSearch,
  Radio,
  Workflow,
} from "lucide-react";
import { isActive } from "@/lib/api";
import type {
  Candidate,
  Citation,
  ProviderCall,
  Snapshot,
  StreamEvent,
} from "@/lib/types";
import { Badge, IconButton } from "./ui";

const PipelineGraph = dynamic(() => import("./pipeline-graph"), {
  ssr: false,
  loading: () => (
    <div className="pipeline-graph graph-loading">
      Opening the live pipeline…
    </div>
  ),
});
const stages = [
  "plan",
  "retrieve",
  "analyze",
  "visualize",
  "answer",
  "finalize",
];

export function Inspector({
  snapshot,
  pipeline,
  metrics,
  connection,
  onSource,
}: {
  snapshot: Snapshot | null;
  pipeline: boolean;
  metrics: boolean;
  connection: string;
  onSource: (citation: Citation) => void;
}) {
  const [stage, setStage] = useState("retrieve");
  const [expanded, setExpanded] = useState(true);
  const [tab, setTab] = useState<"candidates" | "events">("candidates");
  const events = snapshot?.events ?? [];
  const result = events
    .filter((event) => event.type === "retrieval.results")
    .at(-1)?.data;
  const candidates = result?.candidates ?? [];
  if (!pipeline && !metrics) return null;
  const active = isActive(snapshot?.run?.status);
  return (
    <aside className="inspector" aria-label="Live run inspector">
      <div className="inspector-header">
        <div className="inline-controls">
          <span className={`live-dot ${active ? "active" : ""}`} />
          <strong>
            {pipeline ? "Inside this answer" : "Live observability"}
          </strong>
          {snapshot?.run && (
            <Badge>
              {active
                ? connection === "live"
                  ? "Live stream"
                  : connection
                : snapshot.run.status.toLowerCase()}
            </Badge>
          )}
        </div>
        <div className="inline-controls">
          <span className="muted small inspector-helper">
            {active
              ? "Work continues when you leave this page"
              : "Recorded events · no private reasoning"}
          </span>
          <IconButton
            label={expanded ? "Collapse inspector" : "Expand inspector"}
            onClick={() => setExpanded((value) => !value)}
          >
            <ChevronDown size={16} className={expanded ? "rotate-180" : ""} />
          </IconButton>
        </div>
      </div>
      {metrics && <MetricsBar snapshot={snapshot} />}
      {metrics && snapshot && <ProviderLedger snapshot={snapshot} />}
      {metrics && snapshot?.totals && (
        <div className="conversation-totals">
          <span className="eyebrow">CONVERSATION TOTAL</span>
          <span>
            {snapshot.totals.model_calls} model calls ·{" "}
            {snapshot.totals.input_tokens + snapshot.totals.output_tokens}{" "}
            reported tokens
            {snapshot.totals.unknown_usage_calls
              ? ` · ${snapshot.totals.unknown_usage_calls} usage pending/unavailable`
              : ""}
          </span>
          <span className="mono">
            ${Number(snapshot.totals.cost_usd).toFixed(8)} recorded USD
            {snapshot.totals.unknown_cost_calls
              ? ` + ${snapshot.totals.unknown_cost_calls} unknown costs`
              : ""}
          </span>
        </div>
      )}
      {expanded && pipeline && !!snapshot?.run && (
        <>
          <div className="pipeline-stage-tabs" aria-label="Pipeline stages">
            {stages.map((name) => {
              const latest = events
                .filter(
                  (event) =>
                    event.type === "pipeline.stage" &&
                    event.data.stage === name,
                )
                .at(-1)?.data;
              return (
                <button
                  key={name}
                  className={stage === name ? "selected" : ""}
                  onClick={() => setStage(name)}
                >
                  <span className={`stage-status ${latest?.status ?? "idle"}`}>
                    {latest?.status === "completed" ? (
                      <Check size={10} />
                    ) : (
                      stages.indexOf(name) + 1
                    )}
                  </span>
                  {name}
                  <span className="mono">
                    {latest?.duration_ms !== undefined
                      ? `${latest.duration_ms.toFixed(0)} ms`
                      : latest?.status === "running"
                        ? "•••"
                        : "—"}
                  </span>
                </button>
              );
            })}
          </div>
          <PipelineGraph events={events} selected={stage} onSelect={setStage} />
          <div className="inspector-detail">
            <div className="inspector-detail-header">
              <div className="inline-controls">
                <button
                  className={
                    tab === "candidates" ? "text-tab selected" : "text-tab"
                  }
                  onClick={() => setTab("candidates")}
                >
                  <FileSearch size={14} />
                  {stage === "retrieve"
                    ? "Retrieval candidates"
                    : "Stage details"}
                </button>
                <button
                  className={
                    tab === "events" ? "text-tab selected" : "text-tab"
                  }
                  onClick={() => setTab("events")}
                >
                  <Braces size={14} />
                  Event log
                </button>
              </div>
              {result?.mode && (
                <Badge tone={result.mode === "LEXICAL" ? "amber" : "green"}>
                  {result.mode === "LEXICAL"
                    ? "Lexical retrieval"
                    : result.mode === "REUSED_EVIDENCE"
                      ? "Previous answer evidence"
                      : result.mode === "EMPTY"
                        ? "Empty corpus"
                        : "Hybrid retrieval"}
                </Badge>
              )}
            </div>
            {tab === "events" ? (
              <div className="raw-events">
                {events
                  .filter((event) => event.type !== "text.delta")
                  .slice(-30)
                  .reverse()
                  .map((event) => (
                    <div key={event.seq}>
                      <time>
                        {new Date(event.occurred_at).toLocaleTimeString()}
                      </time>
                      <strong>{event.type}</strong>
                      <span>
                        {event.data.stage ||
                          event.data.role ||
                          event.data.tool ||
                          event.data.mode ||
                          ""}
                      </span>
                      <span>{event.data.status || ""}</span>
                      <code>#{event.seq}</code>
                    </div>
                  ))}
                {!events.length && (
                  <p className="muted">
                    Send a question to record the first run.
                  </p>
                )}
              </div>
            ) : stage === "retrieve" ? (
              <>
                <p className="retrieval-explanation">
                  {result?.method ??
                    "Your question is matched against this chatbot’s active document revisions. The real scores and selected chunks appear here."}
                </p>
                <div className="candidate-list">
                  {candidates.slice(0, 8).map((candidate, index) => (
                    <CandidateRow
                      key={candidate.id}
                      candidate={candidate}
                      rank={index + 1}
                      onOpen={() =>
                        onSource({
                          id: `R${index + 1}`,
                          kind: "document",
                          source_id: candidate.source_id,
                          revision_id: candidate.revision_id,
                          revision_number: candidate.revision_number,
                          name: candidate.name,
                          excerpt: candidate.excerpt,
                          locators: candidate.locators,
                        })
                      }
                    />
                  ))}
                  {!candidates.length && (
                    <p className="muted small empty-inspector">
                      {result?.mode === "EMPTY"
                        ? "Add and approve knowledge sources to enable retrieval."
                        : "No retrieval candidates yet."}
                    </p>
                  )}
                </div>
              </>
            ) : (
              <StageDetail
                stage={stage}
                events={events}
                mode={snapshot?.run?.mode}
              />
            )}
          </div>
        </>
      )}
    </aside>
  );
}

function CandidateRow({
  candidate,
  rank,
  onOpen,
}: {
  candidate: Candidate;
  rank: number;
  onOpen: () => void;
}) {
  const page = candidate.locators[0]?.page;
  return (
    <button
      className={`candidate-row ${candidate.selected ? "picked" : ""}`}
      onClick={onOpen}
    >
      <span className="candidate-rank mono">
        {String(rank).padStart(2, "0")}
      </span>
      <div>
        <strong>{candidate.name}</strong>
        <p>{candidate.excerpt.slice(0, 145)}</p>
      </div>
      <div className="candidate-score">
        <span className="mono">
          {candidate.fusion_score === null
            ? "Prior answer"
            : `RRF ${candidate.fusion_score.toFixed(4)}`}
        </span>
        <span>
          {candidate.scores.cosine !== undefined
            ? `cos ${candidate.scores.cosine.toFixed(3)}`
            : candidate.fusion_score === null
              ? "Reused evidence"
              : `lex ${candidate.scores.lexical?.toFixed(3) ?? "—"}`}
        </span>
      </div>
      <span className="candidate-location">
        {candidate.selected ? <Check size={13} /> : ""}p. {page ?? "—"}
        <ArrowUpRight size={12} />
      </span>
    </button>
  );
}

function StageDetail({
  stage,
  events,
  mode,
}: {
  stage: string;
  events: StreamEvent[];
  mode?: string;
}) {
  const plan = events.find((event) => event.type === "plan.ready")?.data;
  const tool = events.find((event) => event.type === "tool.completed")?.data;
  return (
    <div className="stage-detail">
      {stage === "plan" ? (
        <>
          <Database size={20} />
          <h4>
            {plan?.tool === "analyze_dataset"
              ? "Dataset analysis selected"
              : "Document retrieval selected"}
          </h4>
          <p>
            The plan chooses allowed columns, metrics, dates and filters. The
            model cannot execute arbitrary SQL.
          </p>
          {plan?.plan && <pre>{JSON.stringify(plan.plan, null, 2)}</pre>}
        </>
      ) : stage === "analyze" ? (
        <>
          <Database size={20} />
          <h4>
            {tool
              ? `${tool.result?.rows.length} result groups computed`
              : "A deterministic query when needed"}
          </h4>
          <p>
            DuckDB reads the selected dataset revision and computes exact
            counts, sums, averages or failure rates. Source filters and the
            result are saved with this run.
          </p>
          {tool?.result && (
            <pre>{JSON.stringify(tool.result.rows.slice(0, 5), null, 2)}</pre>
          )}
        </>
      ) : stage === "visualize" ? (
        <>
          <Workflow size={20} />
          <h4>Validated visualizations</h4>
          <p>
            Charts use saved analysis rows. Diagrams use a constrained
            node-and-edge specification. No arbitrary generated code runs in
            your browser.
          </p>
        </>
      ) : stage === "answer" ? (
        <>
          <Radio size={20} />
          <h4>
            {mode === "EVIDENCE"
              ? "Evidence mode"
              : "Generate with the selected model"}
          </h4>
          <p>
            {mode === "EVIDENCE"
              ? "Exact analytics and retrieved excerpts are committed incrementally. Configure a public chat provider in Admin for LLM-generated answers."
              : "The selected model receives the question, bounded conversation context and retrieved evidence. Output streams over SSE; provider activity is observable, private reasoning is not shown."}
          </p>
        </>
      ) : (
        <>
          <Check size={20} />
          <h4>Durable answer and audit trail</h4>
          <p>
            The answer, sources, charts, follow-up actions and provider usage
            are stored before the run is marked complete. Reopening the chat
            loads this saved state and catches up any missing events.
          </p>
        </>
      )}
    </div>
  );
}

function MetricsBar({ snapshot }: { snapshot: Snapshot | null }) {
  const [clock, setClock] = useState(() => Date.now());
  const run = snapshot?.run;
  const active = isActive(run?.status);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setClock(Date.now()), 150);
    return () => clearInterval(timer);
  }, [active]);
  const live = useMemo(() => {
    const calls = new Map<
      string,
      Partial<ProviderCall> & {
        estimated_input_tokens?: number;
        input_price_usd_per_million?: number | null;
        output_price_usd_per_million?: number | null;
      }
    >();
    for (const event of snapshot?.events ?? []) {
      if (event.data.call_id && event.type.startsWith("provider."))
        calls.set(event.data.call_id, {
          ...calls.get(event.data.call_id),
          ...event.data,
        });
    }
    const rows = [...calls.values()];
    return {
      input: rows.reduce(
        (sum, call) =>
          sum + (call.input_tokens ?? call.estimated_input_tokens ?? 0),
        0,
      ),
      output: rows.reduce((sum, call) => sum + (call.output_tokens ?? 0), 0),
      cost: rows.reduce((sum, call) => sum + (call.cost_usd ?? 0), 0),
      calls: rows.length,
      pending: rows.some(
        (call) => call.status === undefined || call.status === "STARTED",
      ),
      missing: rows.some(
        (call) =>
          call.cost_status === "UNAVAILABLE" ||
          (call.status !== "COMPLETED" &&
            call.input_price_usd_per_million === null),
      ),
      pendingInputCost: rows
        .filter((call) => !call.status || call.status === "STARTED")
        .reduce(
          (sum, call) =>
            sum +
            ((call.estimated_input_tokens ?? 0) *
              (call.input_price_usd_per_million ?? 0)) /
              1_000_000,
          0,
        ),
      pendingOutputPrice:
        rows.filter((call) => !call.status || call.status === "STARTED").at(-1)
          ?.output_price_usd_per_million ?? 0,
    };
  }, [snapshot?.events]);
  const metrics = run?.metrics;
  const elapsed = run?.started_at
    ? Math.max(
        0,
        (active
          ? clock
          : new Date(run.finished_at ?? run.created_at).getTime()) -
          new Date(run.started_at).getTime(),
      )
    : 0;
  const latency = metrics?.latency_ms ?? elapsed;
  const first =
    metrics?.first_text_ms ??
    (run?.first_text_at && run.started_at
      ? new Date(run.first_text_at).getTime() -
        new Date(run.started_at).getTime()
      : null);
  const outputEstimate = Math.ceil(
    (snapshot?.messages.find(
      (message) => message.run_id === run?.id && message.role === "assistant",
    )?.text.length ?? 0) / 4,
  );
  const modelCalls = metrics?.model_calls ?? live.calls;
  const estimated = active && !!modelCalls;
  const tokens =
    (metrics?.input_tokens ?? live.input) +
    (metrics?.output_tokens ??
      (live.output || (modelCalls ? outputEstimate : 0)));
  const costMissing =
    metrics?.cost_status === "UNAVAILABLE" ||
    live.missing ||
    (!active && live.pending);
  const usageMissing = !active && metrics?.usage_status === "UNAVAILABLE";
  const estimatedCost =
    live.cost +
    live.pendingInputCost +
    (outputEstimate * live.pendingOutputPrice) / 1_000_000;
  return (
    <div className="metrics-bar">
      <div>
        <Clock3 size={14} />
        <span>Latency</span>
        <strong>{run ? `${(latency / 1000).toFixed(2)}s` : "—"}</strong>
      </div>
      <div>
        <Radio size={14} />
        <span>First text</span>
        <strong>
          {first !== null ? `${(first / 1000).toFixed(2)}s` : "—"}
        </strong>
      </div>
      <div>
        <Braces size={14} />
        <span>Tokens {estimated ? "· est." : ""}</span>
        <strong>
          {run
            ? usageMissing
              ? tokens > 0
                ? `${tokens.toLocaleString()}+ (partial)`
                : "Unavailable"
              : `${estimated ? "~" : ""}${tokens.toLocaleString()}`
            : "—"}
        </strong>
      </div>
      <div>
        <Coins size={14} />
        <span>
          Cost · USD
          {active && live.pending
            ? " · est."
            : metrics?.cost_status === "REPORTED"
              ? " · reported"
              : metrics?.cost_status === "CALCULATED"
                ? " · calc."
                : ""}
        </span>
        <strong>
          {costMissing
            ? "Unavailable"
            : active && live.pending
              ? `~$${estimatedCost.toFixed(8)}`
              : run
                ? `$${(metrics?.cost_usd ?? live.cost).toFixed(8)}`
                : "—"}
        </strong>
      </div>
      <div>
        <Activity size={14} />
        <span>Model / tools</span>
        <strong>
          {modelCalls ?? 0} /{" "}
          {metrics?.tool_calls ??
            snapshot?.events.filter((event) => event.type === "tool.started")
              .length ??
            0}
        </strong>
      </div>
      <div className="metric-mode">
        <Badge tone={run?.mode === "EVIDENCE" ? "amber" : "green"}>
          {run?.mode === "EVIDENCE"
            ? "Evidence mode"
            : run
              ? "Provider usage"
              : "Waiting for a run"}
        </Badge>
      </div>
    </div>
  );
}

function ProviderLedger({ snapshot }: { snapshot: Snapshot }) {
  const calls = new Map<
    string,
    {
      role?: string;
      model?: string;
      status?: string;
      input_tokens?: number | null;
      output_tokens?: number | null;
      estimated_input_tokens?: number;
      cost_usd?: number | null;
      cost_status?: string;
      usage_status?: string;
      reasoning_tokens?: number;
      visible_characters?: number;
    }
  >();
  for (const event of snapshot.events) {
    if (event.data.call_id && event.type.startsWith("provider."))
      calls.set(event.data.call_id, {
        ...calls.get(event.data.call_id),
        status:
          event.type === "provider.started" ? "STARTED" : event.data.status,
        ...event.data,
      });
  }
  if (!calls.size) return null;
  return (
    <details className="provider-ledger">
      <summary>Provider attempts · {calls.size} calls</summary>
      <p className="muted small">
        Each attempt is recorded once. Token estimates use conservative
        text/image heuristics; final usage comes from the provider. Calculated
        cost uses the saved pricing version.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Role / model</th>
              <th>State</th>
              <th>Input tokens</th>
              <th>Output tokens</th>
              <th>USD</th>
              <th>Cost basis</th>
            </tr>
          </thead>
          <tbody>
            {[...calls].map(([id, call]) => (
              <tr key={id}>
                <td>
                  {call.role}
                  <small>{call.model}</small>
                </td>
                <td>{call.status}</td>
                <td>
                  {call.input_tokens ??
                    (call.status === "STARTED"
                      ? `~${call.estimated_input_tokens ?? 0}`
                      : "Unavailable")}
                </td>
                <td>
                  {call.output_tokens ??
                    (call.status === "STARTED" ? "Pending" : "Unavailable")}
                  {call.reasoning_tokens !== undefined && (
                    <small>{call.reasoning_tokens} reasoning tokens</small>
                  )}
                  {call.visible_characters !== undefined && (
                    <small>{call.visible_characters} answer characters</small>
                  )}
                </td>
                <td className="mono">
                  {call.cost_usd === undefined || call.cost_usd === null
                    ? call.status === "STARTED"
                      ? "Pending"
                      : "Unavailable"
                    : `$${call.cost_usd.toFixed(8)}`}
                </td>
                <td>{call.cost_status?.toLowerCase() ?? "pending"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
