/* eslint-disable @next/next/no-img-element -- Authenticated source rasters must preserve original geometry and use session cookies. */
"use client";

import { useEffect, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  ScanLine,
  RotateCw,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { api, assetUrl, errorMessage, post } from "@/lib/api";
import type { Citation, DatasetMapping, Revision } from "@/lib/types";
import {
  Badge,
  Button,
  Dialog,
  ErrorBanner,
  IconButton,
  StatusBadge,
} from "./ui";

export type SourceTarget = {
  revision_id: string;
  citation?: Citation;
  review?: boolean;
};
const FINISHED = ["AWAITING_REVIEW", "READY", "READY_LEXICAL", "FAILED"];

export function SourceViewer({
  target,
  onClose,
  onChanged,
  canEdit,
}: {
  target: SourceTarget | null;
  onClose: () => void;
  onChanged: () => void;
  canEdit: boolean;
}) {
  return (
    <Dialog
      open={!!target}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Source evidence"
      description="Original content, pinned to the revision used in the answer."
      className="source-dialog"
    >
      {target && (
        <SourceContent
          key={`${target.revision_id}:${target.citation?.id ?? "review"}`}
          target={target}
          onChanged={onChanged}
          canEdit={canEdit}
        />
      )}
    </Dialog>
  );
}

function SourceContent({
  target,
  onChanged,
  canEdit,
}: {
  target: SourceTarget;
  onChanged: () => void;
  canEdit: boolean;
}) {
  const [revision, setRevision] = useState<Revision | null>(null);
  const [pageNumber, setPageNumber] = useState(
    target.citation?.locators[0]?.page ?? 1,
  );
  const [zoom, setZoom] = useState(100);
  const [rotation, setRotation] = useState(0);
  const [chunks, setChunks] = useState<
    {
      id: string;
      ordinal: number;
      text: string;
      locators: Citation["locators"];
      dimensions: number | null;
      vector_preview: number[] | null;
    }[]
  >([]);
  const [selectedChunk, setSelectedChunk] = useState<
    (typeof chunks)[number] | null
  >(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [remoteConsent, setRemoteConsent] = useState(false);
  const [mapping, setMapping] = useState<DatasetMapping | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [records, setRecords] = useState<{
    columns: string[];
    records: Record<string, string | number | null>[];
    total_matching: number;
    note: string;
  } | null>(null);
  const highlight = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let disposed = false;
    let source: EventSource | undefined;
    let pending: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    async function load() {
      try {
        const row = await api<Revision>(`/revisions/${target.revision_id}`, {
          signal: controller.signal,
        });
        if (disposed) return;
        setRevision(row);
        setMapping((previous) => previous ?? row.dataset?.mapping ?? null);
        setError("");
        if (FINISHED.includes(row.status)) onChanged();
        if (!FINISHED.includes(row.status) && !source) {
          const cursor = row.events.at(-1)?.seq ?? 0;
          source = new EventSource(
            `/api/v1/revisions/${target.revision_id}/events?after=${cursor}`,
          );
          source.addEventListener("update", () => {
            if (pending) return;
            pending = setTimeout(() => {
              pending = undefined;
              void load();
            }, 200);
          });
          source.addEventListener("caught-up", () => {
            source?.close();
            void load();
          });
        }
      } catch (error) {
        if (!disposed) setError(errorMessage(error));
      }
    }
    void load();
    return () => {
      disposed = true;
      controller.abort();
      source?.close();
      if (pending) clearTimeout(pending);
    };
  }, [target.revision_id, refresh, onChanged]);
  useEffect(() => {
    if (!target.citation?.analysis_id) return;
    let disposed = false;
    api<{
      columns: string[];
      records: Record<string, string | number | null>[];
      total_matching: number;
      note: string;
    }>(`/analysis/${target.citation.analysis_id}/records`)
      .then((result) => {
        if (!disposed) setRecords(result);
      })
      .catch((error) => {
        if (!disposed) setError(errorMessage(error));
      });
    return () => {
      disposed = true;
    };
  }, [target.citation?.analysis_id]);
  useEffect(() => {
    if (revision?.extraction?.format !== "pdf" && highlight.current)
      highlight.current.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [revision, pageNumber, selectedChunk?.id]);

  async function approve() {
    setBusy(true);
    setError("");
    try {
      await post(`/revisions/${target.revision_id}/approve`, {
        mapping,
        remote_consent: remoteConsent,
      });
      setRefresh((value) => value + 1);
      onChanged();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  if (!revision)
    return (
      <div className="dialog-body">
        {error ? (
          <ErrorBanner message={error} />
        ) : (
          <p className="muted">Opening the exact source revision…</p>
        )}
      </div>
    );
  const pages = revision.extraction?.pages ?? [];
  const page = pages.find((page) => page.number === pageNumber) ?? pages[0];
  const pageIndex = page ? pages.indexOf(page) : 0;
  const physicalTotal =
    revision.extraction?.total_pages ?? pages.at(-1)?.number ?? pages.length;
  const cited = selectedChunk
    ? {
        id: `C${selectedChunk.ordinal + 1}`,
        kind: "document" as const,
        revision_id: revision.id,
        source_id: revision.source_id,
        name: revision.name,
        excerpt: selectedChunk.text,
        locators: selectedChunk.locators,
      }
    : target.citation;
  const locators =
    cited?.locators.filter((locator) => locator.page === page?.number) ?? [];
  const isNativePage =
    revision.extraction?.format === "pdf" ||
    revision.extraction?.format === "image";
  const highlightedIds = new Set(locators.map((locator) => locator.block_id));
  const fallback = !!cited && !locators.some((locator) => locator.bbox);
  return (
    <>
      <div className="source-title-row">
        <FileText size={19} />
        <div>
          <strong>{revision.name}</strong>
          <p>
            Revision {revision.number} ·{" "}
            {revision.extraction?.parser ?? "Extraction pending"}
          </p>
        </div>
        <StatusBadge status={revision.status} />
        <a
          className="icon-button"
          title="Download original source"
          aria-label="Download original source"
          href={`/api/v1/revisions/${revision.id}/download`}
        >
          <Download size={17} />
        </a>
      </div>
      {error && <ErrorBanner message={error} />}
      {revision.error && <ErrorBanner message={revision.error.message} />}
      <div className="source-layout">
        <div className="source-main">
          <div className="source-toolbar">
            <div className="inline-controls">
              <IconButton
                label="Previous page"
                disabled={pageIndex <= 0}
                onClick={() => setPageNumber(pages[pageIndex - 1]?.number ?? 1)}
              >
                <ChevronLeft size={17} />
              </IconButton>
              <label className="page-input">
                {isNativePage ? "Page" : "Section group"}
                <input
                  aria-label="Source page number"
                  type="number"
                  min={pages[0]?.number ?? 1}
                  max={pages.at(-1)?.number ?? 1}
                  value={page?.number ?? pageNumber}
                  onChange={(event) =>
                    setPageNumber(
                      Math.min(
                        pages.at(-1)?.number ?? 1,
                        Math.max(
                          pages[0]?.number ?? 1,
                          Number(event.target.value) || 1,
                        ),
                      ),
                    )
                  }
                />
                <span>/ {physicalTotal || "—"}</span>
              </label>
              <IconButton
                label="Next page"
                disabled={pageIndex >= pages.length - 1}
                onClick={() => setPageNumber(pages[pageIndex + 1]?.number ?? 1)}
              >
                <ChevronRight size={17} />
              </IconButton>
            </div>
            {isNativePage && (
              <div className="inline-controls">
                <IconButton
                  label="Zoom out"
                  disabled={zoom <= 75}
                  onClick={() => setZoom((value) => value - 25)}
                >
                  <ZoomOut size={16} />
                </IconButton>
                <span className="mono small">{zoom}%</span>
                <IconButton
                  label="Zoom in"
                  disabled={zoom >= 200}
                  onClick={() => setZoom((value) => value + 25)}
                >
                  <ZoomIn size={16} />
                </IconButton>
                <IconButton
                  label="Rotate page clockwise"
                  onClick={() => setRotation((value) => (value + 90) % 360)}
                >
                  <RotateCw size={16} />
                </IconButton>
              </div>
            )}
          </div>
          {fallback && (
            <div className="source-fallback">
              <ScanLine size={15} />
              {isNativePage
                ? "Page-level citation. Precise geometry is unavailable for this generated extraction."
                : "This file has no stable page numbers. The cited section is highlighted below."}
            </div>
          )}
          <div className="source-document-scroll">
            {!page ? (
              <div className="empty-state">
                <ScanLine size={30} />
                <p>
                  {revision.error?.message ||
                    "The source is being parsed. This view updates automatically."}
                </p>
              </div>
            ) : page.image ? (
              <div
                className="page-rotation-frame"
                style={{
                  width: `${zoom}%`,
                  aspectRatio:
                    rotation % 180
                      ? `${page.height ?? 842}/${page.width ?? 595}`
                      : `${page.width ?? 595}/${page.height ?? 842}`,
                }}
              >
                <div
                  className="document-page"
                  style={{
                    width:
                      rotation % 180
                        ? `${((page.width ?? 595) / (page.height ?? 842)) * 100}%`
                        : "100%",
                    transform: `translate(-50%,-50%) rotate(${rotation}deg)`,
                  }}
                >
                  <img
                    src={assetUrl(revision.id, page.image)}
                    alt={`${revision.name}, physical page ${page.number}`}
                    width={page.width}
                    height={page.height}
                  />
                  {locators
                    .filter((locator) => locator.bbox)
                    .map((locator, index) => {
                      const bbox = locator.bbox;
                      if (!bbox) return null;
                      return (
                        <span
                          key={`${locator.block_id}-${index}`}
                          className="source-highlight"
                          aria-label={`Cited ${locator.kind}`}
                          style={{
                            left: `${bbox[0] * 100}%`,
                            top: `${bbox[1] * 100}%`,
                            width: `${(bbox[2] - bbox[0]) * 100}%`,
                            height: `${(bbox[3] - bbox[1]) * 100}%`,
                          }}
                        />
                      );
                    })}
                </div>
              </div>
            ) : (
              <article className="native-document">
                {page.blocks.map((block) => (
                  <div
                    key={block.id}
                    ref={
                      block.id === locators[0]?.block_id ? highlight : undefined
                    }
                    className={
                      highlightedIds.has(block.id)
                        ? "native-block cited-block"
                        : "native-block"
                    }
                    data-anchor={block.id}
                  >
                    {block.type === "heading" ? (
                      <h3>{block.text}</h3>
                    ) : block.rows ? (
                      <div className="table-scroll">
                        <table>
                          <tbody>
                            {block.rows.map((row, index) => (
                              <tr key={index}>
                                {row.map((cell, index) => (
                                  <td key={index}>{cell}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p>{block.text}</p>
                    )}
                    {block.image && (
                      <img
                        src={assetUrl(revision.id, block.image)}
                        alt="Extracted figure"
                      />
                    )}
                    {block.generated && (
                      <Badge tone="amber">Generated interpretation</Badge>
                    )}
                  </div>
                ))}
              </article>
            )}
            {revision.dataset && (
              <div className="dataset-preview">
                <h3>
                  {records
                    ? `Analysis source records · ${records.total_matching.toLocaleString()} match the saved filters`
                    : `Dataset preview · ${revision.dataset.row_count.toLocaleString()} rows`}
                </h3>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        {(
                          records?.columns ??
                          revision.dataset.schema_info.columns.map(
                            (column) => column.name,
                          )
                        ).map((column) => (
                          <th key={column}>{column}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(
                        records?.records ?? revision.dataset.schema_info.sample
                      ).map((row, index) => (
                        <tr key={index}>
                          {(
                            records?.columns ??
                            revision.dataset?.schema_info.columns.map(
                              (column) => column.name,
                            ) ??
                            []
                          ).map((column) => (
                            <td key={column}>{String(row[column] ?? "")}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="muted small">
                  {records
                    ? `First ${records.records.length} matching records. ${records.note}`
                    : "First 12 source records. Analytics citations preserve the query period and filters; row highlights are not inferred from aggregated values."}
                </p>
              </div>
            )}
          </div>
        </div>
        <aside className="source-details">
          {cited && (
            <section>
              <span className="eyebrow">CITED EVIDENCE · {cited.id}</span>
              <p className="citation-excerpt">{cited.excerpt}</p>
              {target.citation?.plan && (
                <div className="context-list">
                  <span>Period</span>
                  <strong>
                    {target.citation.plan.start} → {target.citation.plan.end}
                  </strong>
                  <span>Filter</span>
                  <strong>
                    {target.citation.plan.channel || "All channels"}
                  </strong>
                  <span>Grouping</span>
                  <strong>{target.citation.plan.group_by}</strong>
                </div>
              )}
            </section>
          )}
          <section>
            <span className="eyebrow">EXTRACTION QUALITY</span>
            <div className="quality-grid">
              <div>
                <strong>{pages.length}</strong>
                <span>pages / groups</span>
              </div>
              <div>
                <strong>
                  {
                    pages
                      .flatMap((page) => page.blocks)
                      .filter((block) => block.type === "table").length
                  }
                </strong>
                <span>tables</span>
              </div>
              <div>
                <strong>
                  {
                    pages
                      .flatMap((page) => page.blocks)
                      .filter((block) => block.type === "figure").length
                  }
                </strong>
                <span>figures</span>
              </div>
              <div>
                <strong>{revision.chunk_count}</strong>
                <span>indexed chunks</span>
              </div>
            </div>
            {revision.warnings.map((warning) => (
              <p className="quality-warning" key={warning}>
                {warning}
              </p>
            ))}
            <p className="muted small">
              Method: {revision.processing.method} · Embedding:{" "}
              {revision.embedding_status.toLowerCase().replaceAll("_", " ")}
            </p>
          </section>
          {page?.image && (
            <section>
              <span className="eyebrow">EXTRACTED CONTENT</span>
              <div className="extracted-blocks">
                {page.blocks
                  .filter((block) => block.text || block.image)
                  .map((block) => (
                    <div className="extracted-block" key={block.id}>
                      <Badge tone={block.generated ? "amber" : "neutral"}>
                        {block.type}
                        {block.generated ? " · generated" : ""}
                      </Badge>
                      {block.image && (
                        <img
                          src={assetUrl(revision.id, block.image)}
                          alt="Extracted figure crop"
                        />
                      )}
                      <p>
                        {block.text ||
                          "Figure detected. Enable vision enrichment to describe its contents."}
                      </p>
                    </div>
                  ))}
              </div>
            </section>
          )}
          {canEdit &&
            (revision.status === "AWAITING_REVIEW" ||
              revision.status === "READY_LEXICAL" ||
              (revision.status === "FAILED" && revision.extraction)) && (
              <section className="approval-section">
                <span className="eyebrow">REVIEW & APPROVE</span>
                <p className="muted small">
                  Check extracted values against the original. Approval
                  activates this revision after indexing succeeds.
                </p>
                {revision.dataset && mapping && (
                  <div className="mapping-form">
                    {(
                      ["timestamp", "status", "channel", "amount"] as const
                    ).map((key) => (
                      <label key={key}>
                        {key}
                        <select
                          value={mapping[key] ?? ""}
                          onChange={(event) =>
                            setMapping({
                              ...mapping,
                              [key]: event.target.value || null,
                            })
                          }
                        >
                          <option value="">Not mapped</option>
                          {revision.dataset?.schema_info.columns.map(
                            (column) => (
                              <option value={column.name} key={column.name}>
                                {column.name}
                              </option>
                            ),
                          )}
                        </select>
                      </label>
                    ))}
                    <label>
                      Date format
                      <select
                        value={mapping.date_format ?? "auto"}
                        onChange={(event) =>
                          setMapping({
                            ...mapping,
                            date_format: event.target.value,
                          })
                        }
                      >
                        {[
                          "auto",
                          "%Y-%m-%d",
                          "%Y-%m-%d %H:%M:%S",
                          "%d/%m/%Y",
                          "%d/%m/%Y %H:%M:%S",
                          "%m/%d/%Y",
                          "%m/%d/%Y %H:%M:%S",
                        ].map((format) => (
                          <option key={format} value={format}>
                            {format === "auto"
                              ? "ISO / automatic timezone handling"
                              : format}
                          </option>
                        ))}
                      </select>
                      <span className="muted small">
                        Naive timestamps use Asia/Jakarta; UTC and offset
                        timestamps are converted before filtering.
                      </span>
                    </label>
                    {(
                      [
                        "success_values",
                        "failed_values",
                        "pending_values",
                      ] as const
                    ).map((key) => (
                      <label key={key}>
                        {key.replaceAll("_", " ")}
                        <input
                          value={mapping[key].join(", ")}
                          onChange={(event) =>
                            setMapping({
                              ...mapping,
                              [key]: event.target.value
                                .split(",")
                                .map((value) => value.trim())
                                .filter(Boolean),
                            })
                          }
                        />
                      </label>
                    ))}
                  </div>
                )}
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={remoteConsent}
                    onChange={(event) => setRemoteConsent(event.target.checked)}
                  />
                  <span>
                    Allow approved text to be embedded through OpenRouter. I
                    have permission to share this document with the configured
                    provider.
                  </span>
                </label>
                <Button variant="primary" busy={busy} onClick={approve}>
                  {revision.status === "READY_LEXICAL"
                    ? "Enable vector indexing"
                    : "Approve & index"}
                </Button>
              </section>
            )}
          {revision.events.some((event) =>
            event.type.startsWith("provider."),
          ) && (
            <section>
              <span className="eyebrow">MODEL USAGE FOR THIS REVISION</span>
              <p className="muted small">
                {
                  revision.events.filter(
                    (event) => event.type === "provider.started",
                  ).length
                }{" "}
                calls ·{" "}
                {revision.events
                  .filter((event) => event.type === "provider.finished")
                  .reduce(
                    (sum, event) =>
                      sum +
                      (event.data.input_tokens ?? 0) +
                      (event.data.output_tokens ?? 0),
                    0,
                  )
                  .toLocaleString()}{" "}
                reported tokens
              </p>
              <p className="mono small">
                $
                {revision.events
                  .filter((event) => event.type === "provider.finished")
                  .reduce((sum, event) => sum + (event.data.cost_usd ?? 0), 0)
                  .toFixed(8)}{" "}
                recorded USD
                {revision.events.some(
                  (event) =>
                    event.type === "provider.finished" &&
                    event.data.cost_usd === null,
                )
                  ? " · some costs unavailable"
                  : ""}
              </p>
            </section>
          )}
          {revision.chunk_count > 0 && (
            <section>
              <details
                onToggle={async (event) => {
                  if (event.currentTarget.open && !chunks.length) {
                    try {
                      setChunks(
                        await api<typeof chunks>(
                          `/revisions/${revision.id}/chunks`,
                        ),
                      );
                    } catch (error) {
                      setError(errorMessage(error));
                    }
                  }
                }}
              >
                <summary>Chunks & vector representation</summary>
                <p className="muted small">
                  Select a real indexed chunk to inspect its boundaries and
                  source location.
                </p>
                <div className="chunk-list">
                  {chunks.map((chunk) => (
                    <button
                      key={chunk.id}
                      className={
                        selectedChunk?.id === chunk.id ? "selected" : ""
                      }
                      onClick={() => {
                        setSelectedChunk(chunk);
                        setPageNumber(chunk.locators[0]?.page ?? 1);
                      }}
                    >
                      <span className="mono">
                        C{chunk.ordinal + 1} · p.{" "}
                        {chunk.locators[0]?.page ?? "—"}
                      </span>
                      <p>{chunk.text.slice(0, 120)}…</p>
                      <small>
                        {chunk.dimensions
                          ? `${chunk.dimensions} dimensions`
                          : "Vector indexing pending"}
                      </small>
                    </button>
                  ))}
                </div>
                {selectedChunk?.vector_preview && (
                  <div className="vector-preview">
                    <div>
                      {selectedChunk.vector_preview.map((value, index) => (
                        <span
                          key={index}
                          style={{
                            height: `${Math.min(100, Math.abs(value) * 800 + 4)}%`,
                            background:
                              value >= 0 ? "var(--green)" : "var(--amber)",
                          }}
                        />
                      ))}
                    </div>
                    <p className="muted small">
                      First 16 of {selectedChunk.dimensions} actual vector
                      components. Coordinate illustration; individual dimensions
                      have no named meaning.
                    </p>
                  </div>
                )}
              </details>
            </section>
          )}
          {!!revision.events.length && (
            <section>
              <span className="eyebrow">LIVE INGESTION LOG</span>
              <ol className="event-list">
                {revision.events
                  .filter((event) => event.type.startsWith("ingestion."))
                  .map((event) => (
                    <li key={event.seq}>
                      <span
                        className={
                          event.data.status === "running"
                            ? "event-dot active"
                            : "event-dot"
                        }
                      />
                      <div>
                        <strong>{event.data.stage ?? "Processing"}</strong>
                        <span>
                          {event.data.status ?? event.type.split(".")[1]}
                        </span>
                        {event.data.chunks !== undefined && (
                          <span>{event.data.chunks} chunks</span>
                        )}
                        {event.data.completed !== undefined &&
                          event.data.total !== undefined && (
                            <span>
                              {event.data.completed} / {event.data.total} chunks
                              embedded
                            </span>
                          )}
                        {event.data.pages !== undefined && (
                          <span>
                            {event.data.pages} pages / groups extracted
                          </span>
                        )}
                        {event.data.tables !== undefined && (
                          <span>
                            {event.data.tables} tables ·{" "}
                            {event.data.figures ?? 0} figures
                          </span>
                        )}
                        {event.data.reason && <p>{event.data.reason}</p>}
                      </div>
                    </li>
                  ))}
              </ol>
            </section>
          )}
        </aside>
      </div>
    </>
  );
}
