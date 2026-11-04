"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3, Download, Maximize2, Table2 } from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
import type { ChartBlock, DiagramBlock, VisualBlock } from "@/lib/types";
import { Badge, IconButton } from "./ui";

const PALETTE = [
  "#32856a",
  "#8bbba8",
  "#d3a460",
  "#788caa",
  "#b79ac1",
  "#9c9b72",
];

export function Visualization({
  block,
  showTable = false,
}: {
  block: VisualBlock;
  showTable?: boolean;
}) {
  if (block.type === "notice")
    return (
      <div className="notice">
        <p>{block.message}</p>
      </div>
    );
  return block.type === "chart" ? (
    <Chart block={block} showTable={showTable} />
  ) : (
    <Diagram block={block} />
  );
}

function Chart({
  block,
  showTable,
}: {
  block: ChartBlock;
  showTable: boolean;
}) {
  const [tab, setTab] = useState("chart");
  const [chartType, setChartType] = useState(block.chart_type);
  const [expanded, setExpanded] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const safeData = block.data.slice(0, 100);
  const compareSeries =
    !!block.comparison && block.metric !== "failure_contribution";
  const activeTab = showTable ? "table" : tab;
  const format = (value: number) =>
    `${new Intl.NumberFormat("en", { maximumFractionDigits: 2 }).format(value)}${block.unit === "%" ? "%" : ""}`;
  function saveSvg() {
    const svg = chartRef.current?.querySelector("svg.recharts-surface");
    if (!svg) return;
    const blob = new Blob([new XMLSerializer().serializeToString(svg)], {
      type: "image/svg+xml",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "tampak-chart.svg";
    link.click();
    URL.revokeObjectURL(url);
  }
  const axes = (
    <>
      {compareSeries && <Legend wrapperStyle={{ fontSize: 10 }} />}
      <CartesianGrid
        vertical={false}
        stroke="var(--border)"
        strokeDasharray="3 4"
      />
      <XAxis
        dataKey="label"
        tickLine={false}
        axisLine={false}
        tick={{ fontSize: 11, fill: "var(--muted)" }}
        minTickGap={22}
      />
      <YAxis
        tickLine={false}
        axisLine={false}
        tick={{ fontSize: 11, fill: "var(--muted)" }}
        width={45}
        tickFormatter={(value) =>
          block.unit === "%" ? `${value}%` : String(value)
        }
      />
      <Tooltip
        contentStyle={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          fontSize: 12,
        }}
        formatter={(value) => format(Number(value))}
      />
    </>
  );
  return (
    <section
      className={`visual-card ${expanded ? "expanded-chart" : ""}`}
      aria-label={block.title}
    >
      <div className="visual-heading">
        <div>
          <span className="eyebrow">DATA VISUALIZATION</span>
          <h3>{block.title}</h3>
        </div>
        <Badge tone="green">Exact query</Badge>
      </div>
      <Tabs.Root value={activeTab} onValueChange={setTab}>
        <div className="visual-toolbar">
          <Tabs.List className="segmented" aria-label="Visualization view">
            <Tabs.Trigger value="chart">
              <BarChart3 size={14} />
              Chart
            </Tabs.Trigger>
            <Tabs.Trigger value="table">
              <Table2 size={14} />
              Data
            </Tabs.Trigger>
          </Tabs.List>
          <div className="inline-controls">
            <select
              aria-label="Chart type"
              value={chartType}
              onChange={(event) =>
                setChartType(event.target.value as ChartBlock["chart_type"])
              }
            >
              {[
                "bar",
                "line",
                "area",
                ...(block.unit === "%" || block.metric === "average"
                  ? []
                  : ["pie"]),
              ].map((type) => (
                <option key={type} value={type}>
                  {type[0].toUpperCase() + type.slice(1)}
                </option>
              ))}
            </select>
            <IconButton
              label={expanded ? "Restore chart size" : "Expand chart"}
              onClick={() => setExpanded((value) => !value)}
            >
              <Maximize2 size={15} />
            </IconButton>
            <IconButton label="Download chart as SVG" onClick={saveSvg}>
              <Download size={15} />
            </IconButton>
          </div>
        </div>
        <Tabs.Content value="chart" className="chart-panel">
          <div
            ref={chartRef}
            className="chart-canvas"
            role="img"
            aria-label={`${block.title}. ${safeData.map((row) => `${row.label}: ${row.value === null ? "no value" : format(row.value)}`).join("; ")}`}
          >
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              {chartType === "line" ? (
                <LineChart
                  data={safeData}
                  margin={{ top: 16, right: 20, bottom: 6, left: 0 }}
                >
                  {axes}
                  <Line
                    type="monotone"
                    dataKey="value"
                    name={
                      compareSeries
                        ? "Current period"
                        : (block.metric?.replaceAll("_", " ") ?? "Value")
                    }
                    stroke={PALETTE[0]}
                    strokeWidth={2.5}
                    dot={{ r: 4, fill: "var(--surface)", strokeWidth: 2 }}
                    activeDot={{ r: 6 }}
                    isAnimationActive={false}
                  />
                  {compareSeries && (
                    <Line
                      type="monotone"
                      dataKey="previous"
                      name="Previous period"
                      stroke={PALETTE[3]}
                      strokeWidth={2}
                      strokeDasharray="4 3"
                      dot={{ r: 3 }}
                      isAnimationActive={false}
                    />
                  )}
                </LineChart>
              ) : chartType === "area" ? (
                <AreaChart
                  data={safeData}
                  margin={{ top: 16, right: 20, bottom: 6, left: 0 }}
                >
                  {axes}
                  <Area
                    dataKey="value"
                    name="Current period"
                    stroke={PALETTE[0]}
                    fill={PALETTE[1]}
                    fillOpacity={0.23}
                    strokeWidth={2.5}
                    isAnimationActive={false}
                  />
                  {compareSeries && (
                    <Area
                      dataKey="previous"
                      name="Previous period"
                      stroke={PALETTE[3]}
                      fill={PALETTE[3]}
                      fillOpacity={0.1}
                      isAnimationActive={false}
                    />
                  )}
                </AreaChart>
              ) : chartType === "pie" ? (
                <PieChart>
                  <Pie
                    data={safeData}
                    dataKey="value"
                    nameKey="label"
                    innerRadius="48%"
                    outerRadius="78%"
                    isAnimationActive={false}
                    label
                  >
                    {safeData.map((row, index) => (
                      <Cell
                        key={row.label}
                        fill={PALETTE[index % PALETTE.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              ) : (
                <BarChart
                  data={safeData}
                  margin={{ top: 16, right: 20, bottom: 6, left: 0 }}
                >
                  {axes}
                  <Bar
                    dataKey="value"
                    name={compareSeries ? "Current period" : "Value"}
                    fill={PALETTE[0]}
                    radius={[5, 5, 0, 0]}
                    maxBarSize={64}
                    isAnimationActive={false}
                  />
                  {compareSeries && (
                    <Bar
                      dataKey="previous"
                      name="Previous period"
                      fill={PALETTE[3]}
                      radius={[5, 5, 0, 0]}
                      maxBarSize={64}
                      isAnimationActive={false}
                    />
                  )}
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </Tabs.Content>
        <Tabs.Content value="table">
          <div className="table-scroll">
            <table>
              <caption className="sr-only">
                Exact values used in this visualization
              </caption>
              <thead>
                <tr>
                  {[
                    "Group",
                    "Value",
                    ...(compareSeries ? ["Previous", "Change"] : []),
                    ...(safeData.some((row) => row.failed !== undefined)
                      ? ["Failed", "Completed", "Excluded"]
                      : ["Records"]),
                  ].map((label) => (
                    <th key={label}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {safeData.map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    <td className="mono">
                      {row.value === null ? "—" : format(row.value)}
                    </td>
                    {compareSeries && (
                      <>
                        <td>{row.previous ?? "—"}</td>
                        <td>{row.change ?? "—"}</td>
                      </>
                    )}
                    {row.failed !== undefined ? (
                      <>
                        <td>{row.failed.toLocaleString()}</td>
                        <td>{row.completed?.toLocaleString()}</td>
                        <td>{row.excluded?.toLocaleString()}</td>
                      </>
                    ) : (
                      <td>{row.total?.toLocaleString()}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <a
            className="text-link table-download"
            href={`/api/v1/analysis/${block.analysis_id}/download`}
            download
          >
            <Download size={14} />
            Download these results as CSV
          </a>
        </Tabs.Content>
      </Tabs.Root>
      <div className="visual-foot">
        <p>{block.definition}</p>
        <p className="muted">
          {block.period.start} → {block.period.end_exclusive} (exclusive) ·
          Asia/Jakarta
          {block.filters.channel
            ? ` · ${block.filters.channel}`
            : " · All channels"}
        </p>
        {block.comparison && (
          <p className="muted">
            Baseline: {block.comparison.start} →{" "}
            {block.comparison.end_exclusive} (exclusive).{" "}
            {block.comparison.definition}
          </p>
        )}
        {block.note && <p className="note">{block.note}</p>}
        <span className="mono">[D1] · Source and filters preserved</span>
      </div>
    </section>
  );
}

function Diagram({ block }: { block: DiagramBlock }) {
  const id = useId().replaceAll(":", "");
  const nodes = block.nodes
    .filter((node) => /^n\d+$/.test(node.id))
    .slice(0, 24);
  const ids = new Set(nodes.map((node) => node.id));
  const clean = (text: string) =>
    text.slice(0, 100).replace(/[\u0000-\u001f<>"`\[\]{}\\;|#]/g, " ");
  const edges = block.edges.filter(
    (edge) => ids.has(edge.from) && ids.has(edge.to),
  );
  const definition =
    block.diagram_kind === "sequence"
      ? "sequenceDiagram\n" +
        nodes
          .map((node) => `participant ${node.id} as ${clean(node.label)}`)
          .join("\n") +
        "\n" +
        edges
          .map(
            (edge) =>
              `${edge.from}->>${edge.to}: ${clean(edge.label || "Continue")}`,
          )
          .join("\n")
      : "flowchart LR\n" +
        nodes.map((node) => `${node.id}["${clean(node.label)}"]`).join("\n") +
        "\n" +
        edges
          .map(
            (edge) =>
              `${edge.from} -->${edge.label ? `|${clean(edge.label)}|` : ""} ${edge.to}`,
          )
          .join("\n");
  const [svg, setSvg] = useState("");
  const [error, setError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    async function render() {
      try {
        const [{ default: mermaid }, { default: sanitize }] = await Promise.all(
          [import("mermaid"), import("dompurify")],
        );
        mermaid.initialize({
          startOnLoad: false,
          htmlLabels: false,
          securityLevel: "strict",
          theme: "base",
          themeVariables: {
            primaryColor: "#e4efe9",
            primaryTextColor: "#203d32",
            primaryBorderColor: "#99b7a9",
            lineColor: "#719785",
            fontFamily: "Plus Jakarta Sans, sans-serif",
            fontSize: "13px",
          },
          flowchart: { htmlLabels: false, useMaxWidth: true },
        });
        if (cancelled) return;
        const result = await mermaid.render(
          `diagram${id}${crypto.randomUUID().slice(0, 8)}`,
          definition,
        );
        if (!cancelled)
          setSvg(
            sanitize.sanitize(result.svg, { USE_PROFILES: { svg: true } }),
          );
      } catch {
        if (!cancelled) setError(true);
      }
    }
    void render();
    return () => {
      cancelled = true;
    };
  }, [definition, id]);
  return (
    <section className="visual-card">
      <div className="visual-heading">
        <div>
          <span className="eyebrow">PROCESS DIAGRAM</span>
          <h3>{block.title}</h3>
        </div>
        <Badge>
          {block.basis === "illustrative"
            ? "Illustration"
            : block.citations.length
              ? "From sources"
              : "App workflow"}
        </Badge>
      </div>
      <div className="diagram-panel" aria-label={block.title}>
        {svg ? (
          <div dangerouslySetInnerHTML={{ __html: svg }} />
        ) : (
          <p className="muted">
            {error
              ? "Diagram rendering unavailable. The sequence is shown below."
              : "Rendering diagram…"}
          </p>
        )}
      </div>
      <ol className="diagram-accessible">
        {block.nodes.map((node) => (
          <li key={node.id}>{node.label}</li>
        ))}
      </ol>
    </section>
  );
}
