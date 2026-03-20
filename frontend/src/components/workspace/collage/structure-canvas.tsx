"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  type Connection,
  type Edge,
  type Node,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Loader2Icon, SparklesIcon, Trash2Icon } from "lucide-react";
import { memo, useCallback, useEffect, useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { CollageBlock } from "@/core/documents/collage-blocks";
import { cn } from "@/lib/utils";

// ─── Source colour map (must match collage-workspace) ────────────────────────

const SOURCE_BORDER: Record<string, string> = {
  surfsense: "border-l-blue-500/60",
  calibre: "border-l-amber-500/60",
  chat: "border-l-violet-500/60",
  pasted: "border-l-green-500/60",
  manual: "border-l-zinc-500/60",
  pinboard: "border-l-rose-500/60",
};

const SOURCE_BADGE: Record<string, string> = {
  surfsense: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  calibre: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  chat: "bg-violet-500/20 text-violet-400 border-violet-500/30",
  pasted: "bg-green-500/20 text-green-400 border-green-500/30",
  manual: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
  pinboard: "bg-rose-500/20 text-rose-400 border-rose-500/30",
};

// ─── Custom block node ────────────────────────────────────────────────────────

const BlockNode = memo(function BlockNode({ data }: { data: { block: CollageBlock } }) {
  const { block } = data;
  return (
    <div
      className={cn(
        "w-48 select-none rounded-xl border border-l-[3px] border-border/70 bg-background/95 p-2.5 text-xs shadow-md",
        SOURCE_BORDER[block.source] ?? "border-l-zinc-500/60",
      )}
    >
      <span
        className={cn(
          "mb-1 inline-block rounded border px-1.5 py-0.5 text-[10px] font-medium",
          SOURCE_BADGE[block.source] ?? "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
        )}
      >
        {block.source}
      </span>
      <div className="truncate font-medium leading-snug">{block.title}</div>
      <p className="mt-0.5 line-clamp-2 text-muted-foreground">{block.content}</p>
    </div>
  );
});

const NODE_TYPES = { blockNode: BlockNode };

// ─── Topological sort helpers ─────────────────────────────────────────────────

function topoSort(nodeIds: string[], edges: Edge[]): string[] {
  const adj = new Map<string, string[]>(nodeIds.map((id) => [id, []]));
  const inDegree = new Map<string, number>(nodeIds.map((id) => [id, 0]));

  for (const edge of edges) {
    adj.get(edge.source)?.push(edge.target);
    inDegree.set(edge.target, (inDegree.get(edge.target) ?? 0) + 1);
  }

  const queue = nodeIds.filter((id) => (inDegree.get(id) ?? 0) === 0);
  const result: string[] = [];

  while (queue.length > 0) {
    const node = queue.shift()!;
    result.push(node);
    for (const neighbor of adj.get(node) ?? []) {
      const deg = (inDegree.get(neighbor) ?? 1) - 1;
      inDegree.set(neighbor, deg);
      if (deg === 0) queue.push(neighbor);
    }
  }

  // Append any nodes not reached (disconnected components) in original order
  for (const id of nodeIds) {
    if (!result.includes(id)) result.push(id);
  }

  return result;
}

// ─── StructureCanvas ──────────────────────────────────────────────────────────

export function StructureCanvas({
  blocks,
  synthesizing,
  onSynthesize,
}: {
  blocks: CollageBlock[];
  synthesizing: boolean;
  onSynthesize: (orderedIds?: string[]) => void;
}) {
  const initialNodes: Node[] = useMemo(
    () =>
      blocks.map((block, idx) => ({
        id: block.id,
        type: "blockNode" as const,
        position: { x: 60, y: 60 + idx * 140 },
        data: { block },
        deletable: false,
      })),
    // Only recompute if block IDs change, not the entire blocks array
    [blocks.length],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Sync when blocks list changes (add/remove)
  useEffect(() => {
    setNodes((prev) => {
      const existingIds = new Set(prev.map((n) => n.id));
      const blockIds = new Set(blocks.map((b) => b.id));
      const incoming = blocks.map((block, idx) => ({
        id: block.id,
        type: "blockNode" as const,
        position: prev.find((n) => n.id === block.id)?.position ?? { x: 60, y: 60 + idx * 140 },
        data: { block },
        deletable: false,
      }));
      // Filter existing nodes that are still in blocks, then add new ones
      const filtered = prev.filter((n) => blockIds.has(n.id));
      const added = incoming.filter((n) => !existingIds.has(n.id));
      return [...filtered, ...added];
    });
    // Clean up edges pointing to removed blocks
    setEdges((prev) => {
      const blockIds = new Set(blocks.map((b) => b.id));
      return prev.filter((e) => blockIds.has(e.source) && blockIds.has(e.target));
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blocks.length]);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge({ ...connection, animated: true }, eds)),
    [setEdges],
  );

  function handleStitch() {
    const ordered = topoSort(blocks.map((b) => b.id), edges);
    onSynthesize(ordered);
  }

  function clearEdges() {
    setEdges([]);
  }

  if (blocks.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="rounded-2xl border border-dashed border-border/80 bg-background/60 px-8 py-10 text-center text-xs text-muted-foreground">
          Add blocks from the Materials drawer, then draw edges to define narrative flow.
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex-1">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={NODE_TYPES}
        defaultEdgeOptions={{ style: { strokeWidth: 2 } }}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        className="bg-background/40"
        deleteKeyCode={null}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} className="opacity-30" />
        <Controls showInteractive={false} className="rounded-xl border border-border/60 bg-background/90 shadow-sm" />
      </ReactFlow>

      {/* Floating action bar */}
      <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-xl border border-border/70 bg-background/90 px-3 py-2 shadow-lg backdrop-blur">
        {edges.length > 0 && (
          <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">
            {edges.length} edge{edges.length !== 1 ? "s" : ""}
          </Badge>
        )}
        <Button
          size="sm"
          variant="ghost"
          className="h-7 gap-1 rounded-lg px-2 text-xs text-muted-foreground hover:text-foreground"
          disabled={edges.length === 0}
          onClick={clearEdges}
          title="Clear all edges"
        >
          <Trash2Icon className="size-3" />
          Clear
        </Button>
        <div className="h-4 w-px bg-border" />
        <Button
          size="sm"
          className="h-7 gap-1 rounded-lg px-3 text-xs"
          disabled={synthesizing}
          onClick={handleStitch}
        >
          {synthesizing ? (
            <Loader2Icon className="size-3 animate-spin" />
          ) : (
            <SparklesIcon className="size-3" />
          )}
          Stitch in order
        </Button>
      </div>
    </div>
  );
}
