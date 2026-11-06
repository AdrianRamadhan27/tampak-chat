"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Download,
  FlaskConical,
  Pencil,
  Play,
  Plus,
  Square,
  Trash2,
} from "lucide-react";
import { api, errorMessage, isActive, post } from "@/lib/api";
import type { Bot, Citation, Source } from "@/lib/types";
import {
  Badge,
  Button,
  Dialog,
  EmptyState,
  ErrorBanner,
  StatusBadge,
} from "./ui";

const METRICS = [
  {
    key: "context_precision",
    label: "Context precision",
    group: "Retrieval",
    detail:
      "Ragas average precision: does useful evidence rank ahead of irrelevant passages?",
  },
  {
    key: "context_recall",
    label: "Context recall",
    group: "Retrieval",
    detail:
      "How much of the reference answer can the retrieved evidence support?",
  },
  {
    key: "faithfulness",
    label: "Faithfulness",
    group: "Answer",
    detail:
      "What fraction of the response's claims are supported by its evidence?",
  },
  {
    key: "factual_correctness",
    label: "Factual correctness",
    group: "Answer",
    detail:
      "Ragas claim-level F1 comparing the response with the reference answer.",
  },
] as const;
type MetricKey = (typeof METRICS)[number]["key"];
type Scores = Record<string, number | null>;
type TestCase = {
  id: string;
  title: string;
  question: string;
  reference: string;
  expected_sources: string[];
  required_terms: string[];
  enabled: boolean;
};
type ResultCase = TestCase & {
  status: string;
  response?: string;
  contexts?: string[];
  citations?: Citation[];
  scores: Scores;
  metric_errors: Record<string, { code: string; message: string }>;
  error?: { code: string; message: string };
  latency_ms?: number;
  answer_mode?: string;
};
type Summary = {
  scores?: Scores;
  score_counts?: Record<string, number>;
  total?: number;
  completed?: number;
  failed?: number;
  model_calls?: number;
  cost_usd?: number;
  unknown_cost_calls?: number;
  input_tokens?: number;
  output_tokens?: number;
};
type Evaluation = {
  id: string;
  name: string;
  status: string;
  created_at: string;
  cases?: ResultCase[];
  summary: Summary;
  metrics?: MetricKey[];
  judge: { model: string; version: string; profile_version: number };
  error?: { code: string; message: string };
};

function score(value: number | null | undefined) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function scoreTone(value: number | null | undefined) {
  if (value == null) return "eval-unavailable";
  return value >= 0.8 ? "eval-good" : value >= 0.5 ? "eval-mid" : "eval-low";
}

export default function Evaluations({
  bot,
  sources,
  onCitation,
}: {
  bot: Bot;
  sources: Source[];
  onCitation: (citation: Citation) => void;
}) {
  const [cases, setCases] = useState<TestCase[]>([]);
  const [history, setHistory] = useState<Evaluation[]>([]);
  const [runId, setRunId] = useState("");
  const [run, setRun] = useState<Evaluation | null>(null);
  const [revision, setRevision] = useState(0);
  const [tab, setTab] = useState<"results" | "cases">("results");
  const [inspected, setInspected] = useState("");
  const [editing, setEditing] = useState<TestCase | "new" | null>(null);
  const [deleting, setDeleting] = useState<TestCase | null>(null);
  const [runOpen, setRunOpen] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [metrics, setMetrics] = useState<MetricKey[]>(
    METRICS.map((m) => m.key),
  );
  const [budget, setBudget] = useState("0.25");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const active = isActive(run?.status);

  useEffect(() => {
    let disposed = false;
    async function load() {
      try {
        const [testCases, runs] = await Promise.all([
          api<TestCase[]>(`/bots/${bot.id}/evaluation-cases`),
          api<Evaluation[]>(`/bots/${bot.id}/evaluations`),
        ]);
        if (disposed) return;
        setCases(testCases);
        setHistory(runs);
        const selected = runId || runs[0]?.id;
        if (selected) {
          const detail = await api<Evaluation>(`/evaluations/${selected}`);
          if (disposed) return;
          setRun(detail);
          if (!runId) setRunId(selected);
        }
      } catch (error) {
        if (!disposed) setError(errorMessage(error));
      } finally {
        if (!disposed) setLoading(false);
      }
    }
    void load();
    return () => {
      disposed = true;
    };
  }, [bot.id, revision, runId]);

  useEffect(() => {
    if (!active || !runId) return;
    let disposed = false;
    const timer = window.setInterval(async () => {
      try {
        const detail = await api<Evaluation>(`/evaluations/${runId}`);
        if (disposed) return;
        setRun(detail);
        setHistory((previous) =>
          previous.map((item) => (item.id === detail.id ? detail : item)),
        );
      } catch (error) {
        if (!disposed) setError(errorMessage(error));
      }
    }, 1800);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [active, runId]);

  async function seed() {
    setBusy(true);
    try {
      await post(`/bots/${bot.id}/evaluation-cases/seed`);
      setRevision((v) => v + 1);
      setTab("cases");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  async function start() {
    setBusy(true);
    setError("");
    try {
      const result = await post<Evaluation>(`/bots/${bot.id}/evaluations`, {
        name: `${bot.name} · ${new Date().toLocaleString()}`,
        case_ids: picked,
        metrics,
        request_key: crypto.randomUUID(),
        max_cost_usd: Number(budget),
      });
      setRunOpen(false);
      setRunId(result.id);
      setRun(result);
      setTab("results");
      setRevision((v) => v + 1);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  async function cancel() {
    if (!run) return;
    try {
      await post(`/evaluations/${run.id}/cancel`);
    } catch (error) {
      setError(errorMessage(error));
    }
  }
  async function remove() {
    if (!deleting) return;
    setBusy(true);
    try {
      await api(`/bots/${bot.id}/evaluation-cases/${deleting.id}`, {
        method: "DELETE",
      });
      setDeleting(null);
      setRevision((v) => v + 1);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  function exportResults() {
    if (!run) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(run, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `tampak-evaluation-${run.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }
  const current =
    run?.cases?.find((item) => item.id === inspected) ?? run?.cases?.[0];
  const chart = METRICS.filter((metric) =>
    run?.metrics?.includes(metric.key),
  ).map((metric) => ({
    name: metric.label,
    value:
      run?.summary.scores?.[metric.key] == null
        ? null
        : Number(((run.summary.scores[metric.key] ?? 0) * 100).toFixed(1)),
  }));

  return (
    <div className="content-page evaluation-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">RAG EVALUATION</span>
          <h1>Evidence in. Quality measured.</h1>
          <p>
            Test the actual chatbot, inspect its evidence and compare answers
            against references you control.
          </p>
        </div>
        <div className="eval-actions">
          <Button onClick={() => setEditing("new")}>
            <Plus size={15} />
            Test case
          </Button>
          <Button
            variant="primary"
            disabled={!cases.some((c) => c.enabled) || active}
            onClick={() => {
              setPicked(
                cases
                  .filter((c) => c.enabled)
                  .slice(0, 10)
                  .map((c) => c.id),
              );
              setRunOpen(true);
            }}
          >
            <Play size={15} />
            Run evaluation
          </Button>
        </div>
      </div>
      {error && <ErrorBanner message={error} dismiss={() => setError("")} />}
      <div className="eval-toolbar">
        <div className="eval-actions">
          <Button
            variant={tab === "results" ? "primary" : "ghost"}
            onClick={() => setTab("results")}
          >
            Results
          </Button>
          <Button
            variant={tab === "cases" ? "primary" : "ghost"}
            onClick={() => setTab("cases")}
          >
            Test cases <span className="mono">{cases.length}</span>
          </Button>
        </div>
        <Badge>Administrator workspace</Badge>
      </div>
      {loading ? (
        <p role="status">Loading evaluations…</p>
      ) : tab === "cases" ? (
        <>
          {cases.length ? (
            <div className="eval-case-list">
              {cases.map((item) => (
                <article className="eval-test-case" key={item.id}>
                  <div className="eval-case-title">
                    <div>
                      <h3>{item.title}</h3>
                      <p>{item.question}</p>
                    </div>
                    <div className="eval-actions">
                      <Badge tone={item.enabled ? "green" : undefined}>
                        {item.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                      <Button
                        aria-label={`Edit ${item.title}`}
                        onClick={() => setEditing(item)}
                      >
                        <Pencil size={14} />
                      </Button>
                      <Button
                        aria-label={`Delete ${item.title}`}
                        onClick={() => setDeleting(item)}
                      >
                        <Trash2 size={14} />
                      </Button>
                    </div>
                  </div>
                  <details>
                    <summary>
                      Reference answer and evidence requirements
                    </summary>
                    <p className="eval-reference">{item.reference}</p>
                    <p className="muted">
                      Expected sources:{" "}
                      {item.expected_sources
                        .map(
                          (id) => sources.find((s) => s.id === id)?.name ?? id,
                        )
                        .join(", ") || "Not specified"}
                    </p>
                    <p className="muted">
                      Required evidence phrases:{" "}
                      {item.required_terms.join(", ") || "Not specified"}
                    </p>
                  </details>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<FlaskConical size={28} />}
              title="A reference makes quality testable"
              action={
                bot.is_seed ? (
                  <Button busy={busy} onClick={seed}>
                    Load five NTI example cases
                  </Button>
                ) : (
                  <Button onClick={() => setEditing("new")}>
                    Create test case
                  </Button>
                )
              }
            >
              Add a question, its reviewed reference answer and optional
              evidence requirements.
            </EmptyState>
          )}
        </>
      ) : run ? (
        <>
          <div className="eval-run-header">
            <label>
              Evaluation run
              <select value={runId} onChange={(e) => setRunId(e.target.value)}>
                {history.map((item) => (
                  <option key={item.id} value={item.id}>
                    {new Date(item.created_at).toLocaleString()} · {item.status}
                  </option>
                ))}
              </select>
            </label>
            <div className="eval-actions">
              <StatusBadge status={run.status} />
              {active ? (
                <Button onClick={cancel}>
                  <Square size={13} />
                  Stop
                </Button>
              ) : (
                <Button onClick={exportResults}>
                  <Download size={14} />
                  Export JSON
                </Button>
              )}
            </div>
          </div>
          {run.error && <ErrorBanner message={run.error.message} />}
          <div className="eval-progress">
            <div>
              <strong>
                {run.summary.completed ?? 0}
                <span> / {run.summary.total ?? run.cases?.length ?? 0}</span>
              </strong>
              <p>
                {active
                  ? "Cases finish in the background. You can leave and return."
                  : "Cases finished"}
              </p>
            </div>
            <div>
              <strong>{run.summary.model_calls ?? 0}</strong>
              <p>Generator + judge calls</p>
            </div>
            <div>
              <strong>${Number(run.summary.cost_usd ?? 0).toFixed(5)}</strong>
              <p>
                {run.summary.unknown_cost_calls
                  ? "Partial cost · some calls unavailable"
                  : "Recorded cost"}
              </p>
            </div>
            <div>
              <strong>
                {(
                  (run.summary.input_tokens ?? 0) +
                  (run.summary.output_tokens ?? 0)
                ).toLocaleString()}
              </strong>
              <p>Reported tokens</p>
            </div>
          </div>
          {active && (
            <progress
              className="eval-progress-bar"
              aria-label="Evaluation progress"
              value={run.summary.completed ?? 0}
              max={run.summary.total || 1}
            />
          )}
          <section className="eval-score-section">
            <div className="eval-section-heading">
              <div>
                <h2>Retrieval and answer quality</h2>
                <p>
                  Higher is better. Means include scored cases only; unavailable
                  metrics stay blank.
                </p>
              </div>
              <Badge>Ragas {run.judge.version}</Badge>
            </div>
            <div
              className="eval-chart"
              role="img"
              aria-label="Mean Ragas metric scores from zero to one hundred percent"
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={chart}
                  layout="vertical"
                  margin={{ left: 0, right: 32, top: 8, bottom: 8 }}
                >
                  <CartesianGrid horizontal={false} stroke="var(--border)" />
                  <XAxis
                    type="number"
                    domain={[0, 100]}
                    unit="%"
                    tick={{ fontSize: 11, fill: "var(--muted)" }}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={146}
                    tick={{ fontSize: 12, fill: "var(--ink)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    formatter={(value) => [`${value}%`, "Score"]}
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                    }}
                    cursor={{ fill: "var(--surface-inset)" }}
                  />
                  <Bar
                    dataKey="value"
                    fill="var(--green)"
                    radius={[0, 4, 4, 0]}
                    maxBarSize={24}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="eval-metric-legend">
              {METRICS.filter((m) => run.metrics?.includes(m.key)).map((m) => (
                <div key={m.key}>
                  <span>{m.group}</span>
                  <strong>{score(run.summary.scores?.[m.key])}</strong>
                  <p>
                    {m.label}{" "}
                    <small>n={run.summary.score_counts?.[m.key] ?? 0}</small>
                  </p>
                </div>
              ))}
            </div>
          </section>
          <div className="eval-table-wrap">
            <table className="eval-score-table">
              <thead>
                <tr>
                  <th>Test case</th>
                  {METRICS.map((m) => (
                    <th title={m.detail} key={m.key}>
                      {m.label}
                    </th>
                  ))}
                  <th>Evidence phrases</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {run.cases?.map((item) => (
                  <tr
                    key={item.id}
                    className={current?.id === item.id ? "selected" : ""}
                  >
                    <td>
                      <button onClick={() => setInspected(item.id)}>
                        {item.title}
                      </button>
                    </td>
                    {[...METRICS.map((m) => m.key), "evidence_coverage"].map(
                      (key) => (
                        <td key={key} className={scoreTone(item.scores[key])}>
                          {score(item.scores[key])}
                        </td>
                      ),
                    )}
                    <td>
                      <StatusBadge status={item.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {current && (
            <section className="eval-case-detail">
              <div className="eval-section-heading">
                <div>
                  <span className="eyebrow">INSPECT CASE</span>
                  <h2>{current.title}</h2>
                  <p>{current.question}</p>
                </div>
                <Badge>{current.answer_mode ?? current.status}</Badge>
              </div>
              {current.error && <ErrorBanner message={current.error.message} />}
              <div className="eval-answer-comparison">
                <div>
                  <h3>Reference answer</h3>
                  <p>{current.reference}</p>
                </div>
                <div>
                  <h3>Generated answer</h3>
                  <p className="eval-response">
                    {current.response ||
                      (active
                        ? "Waiting for this case…"
                        : "No answer available.")}
                  </p>
                </div>
              </div>
              <div className="eval-diagnostics">
                <span>
                  Expected source recall{" "}
                  <strong>{score(current.scores.source_recall)}</strong>
                </span>
                <span>
                  Source reciprocal rank{" "}
                  <strong>{score(current.scores.source_mrr)}</strong>
                </span>
                <span>
                  Evidence phrase coverage{" "}
                  <strong>{score(current.scores.evidence_coverage)}</strong>
                </span>
              </div>
              {Object.entries(current.metric_errors).map(([key, issue]) => (
                <p className="eval-metric-error" key={key}>
                  <strong>
                    {METRICS.find((m) => m.key === key)?.label ?? key}:
                  </strong>{" "}
                  {issue.message}
                </p>
              ))}
              <details>
                <summary>
                  Retrieved evidence and exact tool results (
                  {current.contexts?.length ?? 0})
                </summary>
                <div className="eval-citations">
                  {current.citations?.map((citation) => (
                    <Button
                      key={citation.id}
                      onClick={() => onCitation(citation)}
                    >
                      {citation.id} {citation.name}
                    </Button>
                  ))}
                </div>
                {current.contexts?.map((context, i) => (
                  <pre key={i}>{context}</pre>
                ))}
              </details>
            </section>
          )}
          <p className="eval-disclosure">
            Judge: {run.judge.model}, profile v{run.judge.profile_version}. The
            generator and judge share the configured Chat profile. These LLM
            judgments can vary and may share model biases. This authored test
            set measures these cases, not universal quality.
          </p>
          <details className="eval-methods">
            <summary>How the scores work</summary>
            {METRICS.map((m) => (
              <p key={m.key}>
                <strong>{m.label}.</strong> {m.detail}
              </p>
            ))}
            <p>
              Evidence phrase coverage uses case-insensitive literal matching
              against retrieved passages and exact tool output. Source recall
              uses the expected source IDs; reciprocal rank uses citation order.
              These deterministic checks are separate from Ragas scores. Missing
              requirements produce no score.
            </p>
            <p>
              Each run snapshots its cases and active corpus revisions.
              Reference answers are sent only to the judge. Errors and skipped
              scores are excluded from means. Provider calls use the existing
              daily budget plus the evaluation cost limit.
            </p>
            <a
              href="https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/"
              target="_blank"
              rel="noreferrer"
            >
              Ragas metric definitions
            </a>
          </details>
        </>
      ) : (
        <EmptyState
          icon={<FlaskConical size={28} />}
          title="Measure the answer and the evidence"
          action={
            cases.length ? (
              <Button
                onClick={() => {
                  setPicked(
                    cases
                      .filter((c) => c.enabled)
                      .slice(0, 10)
                      .map((c) => c.id),
                  );
                  setRunOpen(true);
                }}
              >
                Choose cases and run
              </Button>
            ) : bot.is_seed ? (
              <Button busy={busy} onClick={seed}>
                Load five NTI example cases
              </Button>
            ) : (
              <Button onClick={() => setEditing("new")}>
                Create test case
              </Button>
            )
          }
        >
          Run questions through the real chatbot, then inspect Ragas scores for
          retrieval and answer synthesis.
        </EmptyState>
      )}
      {editing && (
        <CaseEditor
          key={editing === "new" ? "new" : editing.id}
          botId={bot.id}
          value={editing === "new" ? undefined : editing}
          sources={sources.filter((s) => !s.conversation_id)}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            setRevision((v) => v + 1);
          }}
        />
      )}
      <Dialog
        open={runOpen}
        onOpenChange={setRunOpen}
        title="Run a RAG evaluation"
        description="Generate fresh answers, then score them against your references."
      >
        <div className="eval-run-form">
          {error && <ErrorBanner message={error} />}
          <fieldset>
            <legend>Test cases · choose up to 10</legend>
            {cases
              .filter((c) => c.enabled)
              .map((c) => (
                <label className="eval-check" key={c.id}>
                  <input
                    type="checkbox"
                    checked={picked.includes(c.id)}
                    onChange={(e) =>
                      setPicked((previous) =>
                        e.target.checked
                          ? [...previous, c.id]
                          : previous.filter((id) => id !== c.id),
                      )
                    }
                  />
                  {c.title}
                </label>
              ))}
          </fieldset>
          <fieldset>
            <legend>Ragas judge metrics</legend>
            {METRICS.map((m) => (
              <label className="eval-check" key={m.key}>
                <input
                  type="checkbox"
                  checked={metrics.includes(m.key)}
                  onChange={(e) =>
                    setMetrics((previous) =>
                      e.target.checked
                        ? [...previous, m.key]
                        : previous.filter((key) => key !== m.key),
                    )
                  }
                />
                <span>
                  {m.label}
                  <small>{m.group}</small>
                </span>
              </label>
            ))}
          </fieldset>
          <label className="field">
            Cost limit in USD
            <input
              type="number"
              min="0.01"
              max="2"
              step="0.01"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
          </label>
          <p className="muted">
            Every case generates a real answer using the Chat model. Ragas adds
            paid judge calls. Unchecking all metrics runs generation and
            deterministic evidence checks only. Completed results survive
            navigation; Stop preserves partial work.
          </p>
          <Button
            variant="primary"
            busy={busy}
            disabled={
              !picked.length ||
              picked.length > 10 ||
              !Number.isFinite(Number(budget)) ||
              Number(budget) < 0.01 ||
              Number(budget) > 2
            }
            onClick={start}
          >
            <Play size={14} />
            Evaluate {picked.length} cases
          </Button>
        </div>
      </Dialog>
      <Dialog
        open={!!deleting}
        onOpenChange={() => setDeleting(null)}
        title="Remove this test case?"
        description="Earlier evaluation snapshots retain the reference and results."
      >
        <p>{deleting?.title}</p>
        <div className="form-actions">
          <Button onClick={() => setDeleting(null)}>Keep case</Button>
          <Button variant="danger" busy={busy} onClick={remove}>
            Remove case
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

function CaseEditor({
  botId,
  value,
  sources,
  onClose,
  onSaved,
}: {
  botId: string;
  value?: TestCase;
  sources: Source[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(value?.title ?? "");
  const [question, setQuestion] = useState(value?.question ?? "");
  const [reference, setReference] = useState(value?.reference ?? "");
  const [expected, setExpected] = useState(value?.expected_sources ?? []);
  const [terms, setTerms] = useState(value?.required_terms.join("\n") ?? "");
  const [enabled, setEnabled] = useState(value?.enabled ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save() {
    setBusy(true);
    try {
      await api(
        `/bots/${botId}/evaluation-cases${value ? `/${value.id}` : ""}`,
        {
          method: value ? "PUT" : "POST",
          body: JSON.stringify({
            title,
            question,
            reference,
            expected_sources: expected,
            required_terms: terms
              .split("\n")
              .map((t) => t.trim())
              .filter(Boolean),
            enabled,
          }),
        },
      );
      onSaved();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open
      onOpenChange={onClose}
      title={value ? "Edit test case" : "New test case"}
      description="Write a reviewed reference answer. It is never included in the chatbot's generation prompt."
    >
      <form
        className="eval-editor"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        {error && <ErrorBanner message={error} />}
        <label className="field">
          Title
          <input
            required
            maxLength={120}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label className="field">
          Question
          <textarea
            required
            minLength={3}
            maxLength={2000}
            rows={2}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </label>
        <label className="field">
          Reference answer
          <textarea
            required
            minLength={3}
            maxLength={6000}
            rows={5}
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </label>
        <details>
          <summary>Expected evidence (optional)</summary>
          <fieldset>
            <legend>Expected knowledge sources</legend>
            {sources.map((source) => (
              <label className="eval-check" key={source.id}>
                <input
                  type="checkbox"
                  checked={expected.includes(source.id)}
                  onChange={(e) =>
                    setExpected((previous) =>
                      e.target.checked
                        ? [...previous, source.id]
                        : previous.filter((id) => id !== source.id),
                    )
                  }
                />
                {source.name}
              </label>
            ))}
          </fieldset>
          <label className="field">
            Required evidence phrases · one per line
            <textarea
              rows={3}
              value={terms}
              onChange={(e) => setTerms(e.target.value)}
            />
            <small>
              Literal checks use source-language text, not the generated answer.
            </small>
          </label>
        </details>
        <label className="eval-check">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          Enabled for evaluation
        </label>
        <div className="form-actions">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" busy={busy}>
            Save test case
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
