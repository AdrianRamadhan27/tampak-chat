"use client";

import { useEffect, useState } from "react";
import {
  Check,
  Database,
  LockKeyhole,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { api, errorMessage, post } from "@/lib/api";
import Login from "./login";
import type { CatalogModel, Profile, Session } from "@/lib/types";
import { Badge, Button, ErrorBanner } from "./ui";

type Overview = {
  usage: { calls: number; cost_usd: number; uncertain_calls: number };
  budgets: { global_daily_usd: number; guest_daily_usd: number };
  jobs: { kind: string; status: string; count: number }[];
};

export default function Admin({
  session,
  onSessionChanged,
}: {
  session: Session;
  onSessionChanged: () => Promise<void>;
}) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [runs, setRuns] = useState<
    {
      id: string;
      status: string;
      mode: string;
      created_at: string;
      latency_ms: number | null;
      model_calls: number;
      cost_usd: number;
      unknown_cost_calls: number;
    }[]
  >([]);
  useEffect(() => {
    if (session.kind !== "ADMIN") return;
    let disposed = false;
    Promise.all([
      api<Profile[]>("/admin/profiles"),
      api<Overview>("/admin/overview"),
      api<typeof runs>("/admin/runs"),
    ])
      .then(([profiles, overview, runs]) => {
        if (!disposed) {
          setProfiles(profiles);
          setOverview(overview);
          setRuns(runs);
        }
      })
      .catch((error) => {
        if (!disposed) setError(errorMessage(error));
      });
    return () => {
      disposed = true;
    };
  }, [session.id, session.kind]);
  if (session.kind !== "ADMIN")
    return <Login onSessionChanged={onSessionChanged} />;
  return (
    <div className="content-page admin-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">ADMIN WORKSPACE</span>
          <h1>The models behind the answers.</h1>
          <p>
            Connect compatible providers, choose capabilities and set a public
            demo budget.
          </p>
        </div>
        <Badge tone="green">
          <ShieldCheck size={13} />
          Authenticated admin
        </Badge>
      </div>
      {error && <ErrorBanner message={error} />}
      {overview && (
        <div className="admin-overview">
          <div>
            <span>Today’s provider calls</span>
            <strong className="mono">{overview.usage.calls}</strong>
          </div>
          <div>
            <span>Recorded cost · USD</span>
            <strong className="mono">
              ${Number(overview.usage.cost_usd).toFixed(8)}
            </strong>
          </div>
          <div>
            <span>Calls with unknown cost</span>
            <strong className="mono">{overview.usage.uncertain_calls}</strong>
          </div>
          <div>
            <span>Background workers</span>
            <strong>
              {overview.jobs
                .filter((job) => job.status === "RUNNING")
                .reduce((sum, job) => sum + job.count, 0)}{" "}
              active jobs
            </strong>
          </div>
        </div>
      )}
      <div className="provider-forms">
        {profiles.map((profile) => (
          <ProfileForm
            key={profile.role}
            initial={profile}
            onSaved={async (profile) => {
              setProfiles((previous) =>
                previous.map((item) =>
                  item.role === profile.role ? profile : item,
                ),
              );
              await onSessionChanged();
            }}
          />
        ))}
      </div>
      {overview && <BudgetForm initial={overview.budgets} />}
      <section className="provider-card">
        <div className="section-heading">
          <div>
            <h2>Recent run history</h2>
            <p className="muted small">
              Operational metadata across the demo. Private questions and source
              content are excluded.
            </p>
          </div>
          <Badge>Latest 100 runs</Badge>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Mode</th>
                <th>Started</th>
                <th>Latency</th>
                <th>Calls</th>
                <th>USD</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td className="mono">{run.id.slice(0, 8)}</td>
                  <td>{run.status.toLowerCase()}</td>
                  <td>{run.mode}</td>
                  <td>{new Date(run.created_at).toLocaleString()}</td>
                  <td>
                    {run.latency_ms === null
                      ? "—"
                      : `${(run.latency_ms / 1000).toFixed(2)}s`}
                  </td>
                  <td>{run.model_calls}</td>
                  <td className="mono">
                    ${Number(run.cost_usd).toFixed(8)}
                    {run.unknown_cost_calls ? " + unknown" : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <div className="workspace-note">
        <LockKeyhole size={20} />
        <div>
          <strong>Secrets stay on the server</strong>
          <p>
            API keys are encrypted at rest and never returned to the browser.
            Each provider attempt records its model, configuration version and
            usage. Unknown costs retain their reservation; interrupted attempts
            are retried only by an explicit action.
          </p>
        </div>
      </div>
    </div>
  );
}

function ProfileForm({
  initial,
  onSaved,
}: {
  initial: Profile;
  onSaved: (profile: Profile) => Promise<void>;
}) {
  const [form, setForm] = useState(initial);
  const [key, setKey] = useState("");
  const [clearKey, setClearKey] = useState(false);
  const [catalog, setCatalog] = useState<CatalogModel[]>([]);
  const [catalogFilter, setCatalogFilter] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const pinned = form.role === "EMBEDDING";
  async function save() {
    setBusy("save");
    setError("");
    setMessage("");
    try {
      const body = {
        base_url: form.base_url,
        model: form.model,
        api_key: key || null,
        clear_key: clearKey,
        input_price: form.input_price,
        output_price: form.output_price,
        context_window: form.context_window,
        max_output_tokens: form.max_output_tokens,
        is_public: form.is_public,
        capabilities: form.capabilities,
      };
      const profile = await api<Profile>(`/admin/profiles/${form.role}`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setForm(profile);
      setKey("");
      setClearKey(false);
      setMessage(`Saved configuration v${profile.version}.`);
      await onSaved(profile);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy("");
    }
  }
  async function loadCatalog() {
    setBusy("catalog");
    setError("");
    try {
      const result = await api<{ models: CatalogModel[] }>(
        `/admin/profiles/${form.role}/catalog`,
      );
      setCatalog(result.models);
      setMessage(
        `${result.models.length} models loaded from the saved provider. Select one or enter an ID manually.`,
      );
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy("");
    }
  }
  async function probe() {
    setBusy("probe");
    setError("");
    setMessage("");
    try {
      const result = await post<{
        ok: boolean;
        message: string;
        response?: string;
        dimensions?: number;
      }>(`/admin/profiles/${form.role}/probe`);
      if (!result.ok)
        throw new Error(
          "The provider responded, but the relevance smoke test did not pass.",
        );
      setMessage(
        `${result.message}${result.response ? ` Response: ${result.response}` : ""}${result.dimensions ? ` ${result.dimensions} dimensions.` : ""}`,
      );
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy("");
    }
  }
  function selectModel(id: string) {
    const model = catalog.find((model) => model.id === id);
    setForm((previous) => ({
      ...previous,
      model: id,
      context_window: Math.min(
        131072,
        model?.context_length ?? previous.context_window,
      ),
      input_price:
        model?.pricing?.prompt !== undefined
          ? Number(model.pricing.prompt) * 1_000_000
          : previous.input_price,
      output_price:
        model?.pricing?.completion !== undefined
          ? Number(model.pricing.completion) * 1_000_000
          : previous.output_price,
      capabilities: {
        ...previous.capabilities,
        vision:
          model?.architecture?.input_modalities?.includes("image") ??
          previous.capabilities.vision,
      },
    }));
  }
  const Icon =
    form.role === "CHAT" ? Zap : form.role === "VISION" ? Sparkles : Database;
  return (
    <section className="provider-card">
      <div className="provider-title">
        <div className="provider-icon">
          <Icon size={21} />
        </div>
        <div>
          <h2>
            {form.role === "CHAT"
              ? "Chat model"
              : form.role === "VISION"
                ? "Vision model"
                : "Embedding & vector space"}
          </h2>
          <p>
            {pinned
              ? "Qwen3 Embedding 8B with exact cosine retrieval in PostgreSQL. A different model requires a complete reindex."
              : form.role === "CHAT"
                ? "Planning and streamed, evidence-grounded answers."
                : "Figure descriptions and full-page document interpretation."}
          </p>
        </div>
        <Badge tone={form.configured ? "green" : "amber"}>
          {form.configured ? `Configured · v${form.version}` : "Setup needed"}
        </Badge>
      </div>
      {error && <ErrorBanner message={error} />}
      {message && (
        <div className="success-note" role="status">
          <Check size={15} />
          {message}
        </div>
      )}
      <div className="form-grid">
        <label className="span-two">
          API base URL
          <input
            type="url"
            disabled={pinned}
            value={form.base_url}
            onChange={(event) =>
              setForm({ ...form, base_url: event.target.value })
            }
            placeholder="https://provider.example/v1"
          />
        </label>
        <label className="span-two">
          Model ID
          <div className="input-action">
            <input
              disabled={pinned}
              value={form.model}
              onChange={(event) =>
                setForm({ ...form, model: event.target.value })
              }
              placeholder="provider/model-name"
            />
            <Button
              onClick={loadCatalog}
              busy={busy === "catalog"}
              disabled={!!busy || form.base_url !== initial.base_url}
            >
              <RefreshCw size={14} />
              Catalog
            </Button>
          </div>
        </label>
        {!!catalog.length && !pinned && (
          <div className="catalog-picker span-two">
            <input
              aria-label={`Search ${form.role.toLowerCase()} model catalog`}
              placeholder="Filter models…"
              value={catalogFilter}
              onChange={(event) => setCatalogFilter(event.target.value)}
            />
            <select
              aria-label={`${form.role.toLowerCase()} model catalog`}
              size={5}
              onChange={(event) => selectModel(event.target.value)}
              value={form.model}
            >
              {catalog
                .filter((model) =>
                  `${model.id} ${model.name}`
                    .toLowerCase()
                    .includes(catalogFilter.toLowerCase()),
                )
                .slice(0, 100)
                .map((model) => (
                  <option value={model.id} key={model.id}>
                    {model.name} · {model.id}
                  </option>
                ))}
            </select>
          </div>
        )}
        <label className="span-two">
          API key{" "}
          <span className="muted small">
            {form.has_key
              ? "Stored securely · leave empty to keep"
              : "No stored key"}
          </span>
          <input
            type="password"
            autoComplete="new-password"
            value={key}
            onChange={(event) => setKey(event.target.value)}
            placeholder={
              form.has_key ? "•••••••••••• (unchanged)" : "Paste provider key"
            }
          />
        </label>
        {!pinned && (
          <>
            <label>
              Input · USD / 1M tokens
              <input
                type="number"
                min={0}
                step="any"
                placeholder="Unknown"
                value={form.input_price ?? ""}
                onChange={(event) =>
                  setForm({
                    ...form,
                    input_price:
                      event.target.value === ""
                        ? null
                        : Number(event.target.value),
                  })
                }
              />
            </label>
            <label>
              Output · USD / 1M tokens
              <input
                type="number"
                min={0}
                step="any"
                placeholder="Unknown"
                value={form.output_price ?? ""}
                onChange={(event) =>
                  setForm({
                    ...form,
                    output_price:
                      event.target.value === ""
                        ? null
                        : Number(event.target.value),
                  })
                }
              />
            </label>
            <label>
              Context window
              <input
                type="number"
                min={2048}
                max={131072}
                value={form.context_window}
                onChange={(event) =>
                  setForm({
                    ...form,
                    context_window: Number(event.target.value),
                  })
                }
              />
            </label>
            <label>
              Maximum output tokens
              <input
                type="number"
                min={32}
                max={8192}
                value={form.max_output_tokens}
                onChange={(event) =>
                  setForm({
                    ...form,
                    max_output_tokens: Number(event.target.value),
                  })
                }
              />
            </label>
          </>
        )}
      </div>
      <div className="provider-capabilities">
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={form.is_public}
            onChange={(event) =>
              setForm({ ...form, is_public: event.target.checked })
            }
          />
          Allow demo visitors to use this provider
        </label>
        {!pinned && (
          <>
            {form.base_url.includes("openrouter.ai") && (
              <label>
                Reasoning mode
                <select
                  value={form.capabilities.reasoning_mode ?? "auto"}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      capabilities: {
                        ...form.capabilities,
                        reasoning_mode: event.target.value as NonNullable<
                          Profile["capabilities"]["reasoning_mode"]
                        >,
                      },
                    })
                  }
                >
                  <option value="auto">Provider default</option>
                  <option value="off">Off · direct answers</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
                <span className="muted small">
                  Reasoning shares the output-token allowance. Support depends
                  on the selected model.
                </span>
              </label>
            )}
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={form.capabilities.vision ?? false}
                onChange={(event) =>
                  setForm({
                    ...form,
                    capabilities: {
                      ...form.capabilities,
                      vision: event.target.checked,
                    },
                  })
                }
              />
              Image input
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={form.capabilities.stream_usage ?? true}
                onChange={(event) =>
                  setForm({
                    ...form,
                    capabilities: {
                      ...form.capabilities,
                      stream_usage: event.target.checked,
                    },
                  })
                }
              />
              Streaming usage supported
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={form.capabilities.keyless ?? false}
                onChange={(event) =>
                  setForm({
                    ...form,
                    capabilities: {
                      ...form.capabilities,
                      keyless: event.target.checked,
                    },
                  })
                }
              />
              Local provider requires no key
            </label>
          </>
        )}
        {form.has_key && (
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={clearKey}
              onChange={(event) => setClearKey(event.target.checked)}
            />
            Remove stored key on save
          </label>
        )}
      </div>
      {pinned && (
        <div className="embedding-spec">
          <Badge>4096 dimensions</Badge>
          <Badge>Cosine · exact search</Badge>
          <Badge>USD {form.input_price ?? "—"} / 1M input tokens</Badge>
          <p>
            Requests use OpenRouter with a $0.01 per million input-token price
            cap. Run the query/document relevance probe and index each approved
            source from Knowledge. Embeddings from different models are never
            mixed.
          </p>
        </div>
      )}
      <div className="provider-footer">
        <span className="muted small">
          {form.base_url !== initial.base_url
            ? "Save the new base URL before loading its catalog."
            : "Manual model IDs work with compatible providers."}
        </span>
        <Button
          disabled={!!busy || !form.configured}
          busy={busy === "probe"}
          onClick={probe}
        >
          Test saved configuration
        </Button>
        <Button
          variant="primary"
          disabled={!!busy}
          busy={busy === "save"}
          onClick={save}
        >
          <Save size={14} />
          Save provider
        </Button>
      </div>
    </section>
  );
}

function BudgetForm({ initial }: { initial: Overview["budgets"] }) {
  const [form, setForm] = useState(initial);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await api("/admin/budgets", {
        method: "PUT",
        body: JSON.stringify(form),
      });
      setMessage("Budget limits saved.");
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="provider-card" onSubmit={save}>
      <div className="section-heading">
        <div>
          <h2>Public demo budget</h2>
          <p className="muted">
            Reserve an upper bound before each call. Limits reset daily at UTC
            midnight.
          </p>
        </div>
        <Badge>
          <ShieldCheck size={12} />
          Enforced on the server
        </Badge>
      </div>
      <div className="form-grid">
        <label>
          Global daily limit · USD
          <input
            type="number"
            min={0}
            max={1000}
            step="0.01"
            value={form.global_daily_usd}
            onChange={(event) =>
              setForm({ ...form, global_daily_usd: Number(event.target.value) })
            }
          />
        </label>
        <label>
          Per guest daily limit · USD
          <input
            type="number"
            min={0}
            max={10}
            step="0.01"
            value={form.guest_daily_usd}
            onChange={(event) =>
              setForm({ ...form, guest_daily_usd: Number(event.target.value) })
            }
          />
        </label>
      </div>
      <div className="provider-footer">
        <span role="status" className="muted small">
          {message ||
            "A public provider needs known pricing. Unknown usage remains visible."}
        </span>
        <Button type="submit" busy={busy}>
          Save budget
        </Button>
      </div>
    </form>
  );
}
