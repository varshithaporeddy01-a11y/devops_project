"use client";

import { useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  NodeMouseHandler,
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
  const childEdges = edges.filter((e) => e.type === "child" || e.type === "import");
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
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const positions = useMemo(() => computeLayout(nodes, edges), [nodes, edges]);
  const related = useMemo(() => {
    const dependencies = edges.filter((edge) => edge.type === "call" || edge.type === "import");
    const upstream = new Set<string>();
    const downstream = new Set<string>();
    if (!selectedNode) return { upstream, downstream, edgeIds: new Set<string>() };
    const walk = (start: string, incoming: boolean, visited: Set<string>) => {
      const queue = [start];
      visited.add(start);
      while (queue.length) {
        const current = queue.shift()!;
        for (const edge of dependencies) {
          const next = incoming
            ? edge.target === current ? edge.source : null
            : edge.source === current ? edge.target : null;
          if (next && !visited.has(next)) { visited.add(next); queue.push(next); }
        }
      }
    };
    walk(selectedNode, true, upstream);
    walk(selectedNode, false, downstream);
    const pathNodes = new Set([...upstream, ...downstream, selectedNode]);
    const edgeIds = new Set(dependencies.filter((edge) => pathNodes.has(edge.source) && pathNodes.has(edge.target)).map((edge) => edge.id));
    return { upstream, downstream, edgeIds };
  }, [edges, selectedNode]);

  const flowNodes: Node[] = useMemo(
    () =>
      nodes.map((n) => {
        const pos = positions.get(n.id) ?? { x: 0, y: 0 };
        const isActive =
          activeLine !== null && n.startLine <= activeLine && activeLine <= n.endLine;
        const isSelected = selectedNode === n.id;
        const isRelated = related.upstream.has(n.id) || related.downstream.has(n.id);
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
            background: isSelected ? `${color}66` : isRelated ? `${color}2b` : isActive ? `${color}33` : "#191c26",
            color: "#eef0f5",
            fontSize: 12,
            fontFamily: "JetBrains Mono, ui-monospace, monospace",
            padding: "8px 10px",
            width: 200,
            boxShadow: isSelected ? `0 0 0 3px ${color}` : isActive ? `0 0 0 2px ${color}` : "none",
          },
        };
      }),
    [nodes, positions, activeLine, selectedNode, related]
  );

  const flowEdges: Edge[] = useMemo(
    () =>
      edges
        .filter((e) => e.type === "child" || e.type === "call" || e.type === "import")
        .map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.type === "call" ? "calls" : e.type === "import" ? "imports" : undefined,
          animated: related.edgeIds.has(e.id),
          style: {
            stroke: related.edgeIds.has(e.id) ? "#e8a33d" : e.type === "call" ? "#5b9ee8" : e.type === "import" ? "#9aa2b8" : "#333849",
            strokeWidth: related.edgeIds.has(e.id) ? 2.5 : 1,
            strokeDasharray: e.type === "call" || e.type === "import" ? "5 4" : undefined,
          },
          markerEnd: { type: MarkerType.ArrowClosed, color: related.edgeIds.has(e.id) ? "#e8a33d" : "#333849" },
        })),
    [edges, related.edgeIds]
  );

  const handleNodeClick: NodeMouseHandler = (_event, node) => setSelectedNode(node.id);

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
      onNodeClick={handleNodeClick}
      onPaneClick={() => setSelectedNode(null)}
      fitView
      proOptions={{ hideAttribution: true }}
      className="bg-ink-950"
    >
      <Background color="#242836" gap={20} />
      <Controls className="!bg-ink-800 !text-paper" />
    </ReactFlow>
  );
}
