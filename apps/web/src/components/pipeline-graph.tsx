"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  MarkerType,
  Position,
  ReactFlow,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { StreamEvent } from "@/lib/types";

export const STAGES = [
  { id: "plan", label: "Understand", detail: "Select a constrained tool plan" },
  {
    id: "retrieve",
    label: "Retrieve",
    detail: "Rank and select source chunks",
  },
  { id: "analyze", label: "Analyze", detail: "Query the dataset exactly" },
  {
    id: "visualize",
    label: "Visualize",
    detail: "Validate charts and diagrams",
  },
  {
    id: "answer",
    label: "Answer",
    detail: "Generate an evidence-grounded response",
  },
  {
    id: "finalize",
    label: "Finish",
    detail: "Save sources, actions and usage",
  },
];

export function stageState(events: StreamEvent[], id: string) {
  return events
    .filter(
      (event) => event.type === "pipeline.stage" && event.data.stage === id,
    )
    .at(-1)?.data;
}

const compactPositions = [
  { x: 0, y: 0, source: Position.Right, target: Position.Left },
  { x: 180, y: 0, source: Position.Bottom, target: Position.Left },
  { x: 180, y: 100, source: Position.Left, target: Position.Top },
  { x: 0, y: 100, source: Position.Bottom, target: Position.Right },
  { x: 0, y: 200, source: Position.Right, target: Position.Top },
  { x: 180, y: 200, source: Position.Right, target: Position.Left },
];

export default function PipelineGraph({
  events,
  selected,
  onSelect,
}: {
  events: StreamEvent[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [compact, setCompact] = useState(true);
  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver(([entry]) => {
      setCompact(entry.contentRect.width < 640);
    });
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const nodes: Node[] = useMemo(
    () =>
      STAGES.map((stage, index) => {
        const state = stageState(events, stage.id);
        return {
          id: stage.id,
          style: { width: 118 },
          sourcePosition: compact
            ? compactPositions[index].source
            : Position.Right,
          targetPosition: compact
            ? compactPositions[index].target
            : Position.Left,
          position: compact
            ? { x: compactPositions[index].x, y: compactPositions[index].y }
            : { x: index * 150, y: 0 },
          data: {
            label: (
              <div>
                <span className="graph-step-number">0{index + 1}</span>
                <strong>{stage.label}</strong>
                <span>
                  {state?.duration_ms !== undefined
                    ? `${state.duration_ms.toFixed(0)} ms`
                    : state?.status === "running"
                      ? "In progress"
                      : "Waiting"}
                </span>
              </div>
            ),
          },
          className: `pipeline-node ${state?.status ?? "idle"} ${selected === stage.id ? "selected" : ""}`,
          selectable: true,
          draggable: false,
          connectable: false,
        };
      }),
    [events, selected, compact],
  );
  const edges: Edge[] = useMemo(
    () =>
      STAGES.slice(1).map((stage, index) => ({
        id: `e${index}`,
        type: "smoothstep",
        markerEnd: { type: MarkerType.ArrowClosed, color: "#719785" },
        source: STAGES[index].id,
        target: stage.id,
        animated: stageState(events, stage.id)?.status === "running",
        className: stageState(events, stage.id) ? "edge-active" : "",
      })),
    [events],
  );
  return (
    <div
      ref={container}
      className={`pipeline-graph ${compact ? "compact" : ""}`}
      aria-label="Live retrieval and generation pipeline"
    >
      <ReactFlow
        key={compact ? "compact" : "horizontal"}
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.08 }}
        minZoom={0.25}
        maxZoom={1.1}
        nodesDraggable={false}
        nodesConnectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        onNodeClick={(_, node) => onSelect(node.id)}
      >
        <Background color="var(--border)" gap={16} />
      </ReactFlow>
    </div>
  );
}
