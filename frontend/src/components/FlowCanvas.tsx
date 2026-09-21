"use client";

import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  MarkerType,
  Node,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";
import type { GraphEdge, GraphNode, NodeCategory } from "@/lib/types";

const CATEGORY_COLOR: Record<NodeCategory, string> = {
  module: "#4a5068",
  function: "#8b7cf6",
  loop: "#e8a33d",
  condition: "#f0648c",
  variable: "#3fc5b7",
  call: "#5b9ee8",
  return: "#5fd68f",
  import: "#9aa2b8",
  class: "#e0857a",
};

interface FlowCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  activeLine: number | null;
}

/** Simple layered (Sugiyama-lite) layout using only "child" edges as the tree. */
function computeLayout(nodes: GraphNode[], edges: GraphEdge[]) {
  const childEdges = edges.filter((e) => e.type === "child");
  const childrenOf = new Map<string, string[]>();
  const hasParent = new Set<string>();

  for (const edge of childEdges) {
    const list = childrenOf.get(edge.source) ?? [];
    list.push(edge.target);
    childrenOf.set(edge.source, list);
    hasParent.add(edge.target);
  }

  const roots = nodes.filter((n) => !hasParent.has(n.id));
  const depthOf = new Map<string, number>();
  const columnCounter = new Map<number, number>();
  const positions = new Map<string, { x: number; y: number }>();

  const NODE_W = 220;
  const NODE_H = 90;

  function place(id: string, depth: number) {
    depthOf.set(id, depth);
    const col = columnCounter.get(depth) ?? 0;
    columnCounter.set(depth, col + 1);
    positions.set(id, { x: col * NODE_W, y: depth * NODE_H });
    for (const childId of childrenOf.get(id) ?? []) {
      place(childId, depth + 1);
    }
  }

  roots.forEach((root) => place(root.id, 0));

  // Any nodes unreached (shouldn't normally happen) get placed at depth 0.
  for (const n of nodes) {
    if (!positions.has(n.id)) {
      place(n.id, 0);
    }
  }

  return positions;
}

export default function FlowCanvas({ nodes, edges, activeLine }: FlowCanvasProps) {
  const positions = useMemo(() => computeLayout(nodes, edges), [nodes, edges]);

  const flowNodes: Node[] = useMemo(
    () =>
      nodes.map((n) => {
        const pos = positions.get(n.id) ?? { x: 0, y: 0 };
        const isActive =
          activeLine !== null && n.startLine <= activeLine && activeLine <= n.endLine;
        const color = CATEGORY_COLOR[n.category] ?? CATEGORY_COLOR.module;
        return {
          id: n.id,
          position: pos,
          sourcePosition: Position.Bottom,
          targetPosition: Position.Top,
          data: { label: n.label },
          style: {
            border: `1.5px solid ${color}`,
            borderRadius: 8,
            background: isActive ? `${color}33` : "#191c26",
            color: "#eef0f5",
            fontSize: 12,
            fontFamily: "JetBrains Mono, ui-monospace, monospace",
            padding: "8px 10px",
            width: 200,
            boxShadow: isActive ? `0 0 0 2px ${color}` : "none",
          },
        };
      }),
    [nodes, positions, activeLine]
  );

  const flowEdges: Edge[] = useMemo(
    () =>
      edges
        .filter((e) => e.type === "child")
        .map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          animated: false,
          style: { stroke: "#333849" },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#333849" },
        })),
    [edges]
  );

  if (nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-paper/40">
        Run your code to see its structure here.
      </div>
    );
  }

  return (
    <ReactFlow
      nodes={flowNodes}
      edges={flowEdges}
      fitView
      proOptions={{ hideAttribution: true }}
      className="bg-ink-950"
    >
      <Background color="#242836" gap={20} />
      <Controls className="!bg-ink-800 !text-paper" />
    </ReactFlow>
  );
}
