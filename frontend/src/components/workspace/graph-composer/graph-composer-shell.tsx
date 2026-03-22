"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type ReactFlowInstance,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  ArrowRightLeftIcon,
  BookMarkedIcon,
  FileDownIcon,
  FileSymlinkIcon,
  FolderTreeIcon,
  GitCompareArrowsIcon,
  GripIcon,
  Loader2Icon,
  MilestoneIcon,
  MousePointerClickIcon,
  PanelLeftOpenIcon,
  PlusIcon,
  RefreshCwIcon,
  SaveIcon,
  ScrollTextIcon,
  SplinePointerIcon,
  Trash2Icon,
} from "lucide-react";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { LifecyclePill } from "@/components/workspace/lifecycle-pill";
import { loadBlocks, type BlockSource } from "@/core/documents/collage-blocks";
import {
  compileGraphDocument,
  convertBlockToSourceNode,
  hashString,
  isGraphStaleAgainstMarkdown,
  normalizeComposerState,
  seedGraphFromMarkdown,
  withGraphComposer,
  type ComposerStateEnvelope,
  type GraphComposerDocument,
  type GraphComposerEdge,
  type GraphComposerNode,
  type GraphEdgeKind,
  type GraphNodeKind,
  type GraphSectionFrame,
} from "@/core/documents/composer-state";
import { useUpdateDocument } from "@/core/documents/hooks";
import type { DocumentRecord } from "@/core/documents/types";
import { cn } from "@/lib/utils";

import { GraphNodeEditor } from "./graph-node-editor";

const SOURCE_BADGES: Record<BlockSource | "document", string> = {
  surfsense: "bg-blue-500/15 text-blue-700 border-blue-500/30 dark:text-blue-300",
  calibre: "bg-amber-500/15 text-amber-700 border-amber-500/30 dark:text-amber-300",
  chat: "bg-violet-500/15 text-violet-700 border-violet-500/30 dark:text-violet-300",
  pasted: "bg-emerald-500/15 text-emerald-700 border-emerald-500/30 dark:text-emerald-300",
  manual: "bg-zinc-500/15 text-zinc-700 border-zinc-500/30 dark:text-zinc-300",
  pinboard: "bg-rose-500/15 text-rose-700 border-rose-500/30 dark:text-rose-300",
  document: "bg-slate-500/15 text-slate-700 border-slate-500/30 dark:text-slate-300",
};

const NODE_STYLES: Record<GraphNodeKind, string> = {
  section: "border-sky-700/30 bg-sky-100/70",
  paragraph: "border-stone-700/15 bg-amber-50/80",
  evidence: "border-emerald-700/20 bg-emerald-50/85",
  quote: "border-violet-700/20 bg-violet-50/85",
  transition: "border-orange-700/20 bg-orange-50/85",
  note: "border-zinc-700/20 bg-zinc-100/85",
  source: "border-blue-700/20 bg-blue-50/90",
  rewrite: "border-rose-700/20 bg-rose-50/90",
};

const EDGE_COLORS: Record<GraphEdgeKind, string> = {
  supports: "#0f766e",
  contradicts: "#b91c1c",
  references: "#475569",
  "rewrite-of": "#9f1239",
};

const NODE_LABELS: Record<GraphNodeKind, string> = {
  section: "Section",
  paragraph: "Paragraph",
  evidence: "Evidence",
  quote: "Quote",
  transition: "Transition",
  note: "Note",
  source: "Source",
  rewrite: "Rewrite",
};

const SOURCE_PRIORITY: BlockSource[] = ["calibre", "pinboard", "surfsense", "chat", "pasted", "manual"];
const SOURCE_DISPLAY_LABEL: Record<BlockSource, string> = {
  calibre: "Calibre",
  pinboard: "Pinboard",
  surfsense: "SurfSense",
  chat: "Chat",
  pasted: "Pasted",
  manual: "Manual",
};

function nextId(prefix: string) {
  return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
}

function getDefaultNodeContent(kind: GraphNodeKind) {
  switch (kind) {
    case "section":
      return "New section";
    case "evidence":
      return "- Add supporting facts\n- Add grounding details";
    case "quote":
      return "Add a quoted passage or sourced language.";
    case "transition":
      return "Bridge the previous idea into the next one.";
    case "note":
      return "Add an editorial note or unresolved question.";
    case "source":
      return "Imported source material.";
    case "rewrite":
      return "Alternative phrasing or alternate branch.";
    default:
      return "Write the next part of the draft here.";
  }
}

function frameHeightFor(frameId: string, nodes: GraphComposerNode[]) {
  const count = nodes.filter((node) => node.sectionId === frameId).length;
  return Math.max(760, 180 + (count * 150));
}

function pointInsideFrame(point: { x: number; y: number }, frame: GraphSectionFrame) {
  return (
    point.x >= frame.position.x
    && point.x <= frame.position.x + frame.width
    && point.y >= frame.position.y
    && point.y <= frame.position.y + frame.height
  );
}

const SectionFrameNode = memo(function SectionFrameNode({
  data,
}: {
  data: {
    frame: GraphSectionFrame;
    count: number;
  };
}) {
  return (
    <div className="h-full w-full rounded-[28px] border border-stone-700/15 bg-[linear-gradient(180deg,rgba(255,251,235,0.88),rgba(255,247,237,0.72))] shadow-[0_30px_80px_rgba(120,53,15,0.08)]">
      <div className="flex items-center justify-between border-b border-stone-700/10 px-4 py-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.22em] text-stone-500">Section Frame</div>
          <div className="text-base font-semibold text-stone-900">{data.frame.title}</div>
        </div>
        <Badge variant="outline" className="border-stone-400/30 bg-white/70 text-stone-600">
          {data.count} cards
        </Badge>
      </div>
    </div>
  );
});

const EditorialNode = memo(function EditorialNode({
  data,
  selected,
}: {
  data: {
    node: GraphComposerNode;
    activeRewriteIds: string[];
    onChange: (nodeId: string, patch: Partial<GraphComposerNode>) => void;
    onActivateRewrite: (nodeId: string) => void;
  };
  selected: boolean;
}) {
  const { node } = data;
  const isActiveRewrite = node.kind === "rewrite" && data.activeRewriteIds.includes(node.id);

  return (
    <div
      className={cn(
        "w-[270px] rounded-[22px] border p-3 shadow-[0_16px_40px_rgba(15,23,42,0.12)] transition-all",
        NODE_STYLES[node.kind],
        selected && "ring-2 ring-stone-900/20",
      )}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="space-y-1">
          <Badge variant="outline" className="bg-white/70 text-[10px] uppercase tracking-[0.14em]">
            {NODE_LABELS[node.kind]}
          </Badge>
          {node.source ? (
            <Badge variant="outline" className={cn("bg-white/70 text-[10px]", SOURCE_BADGES[node.source])}>
              {node.source}
            </Badge>
          ) : null}
        </div>
        {node.kind === "rewrite" ? (
          <Button
            type="button"
            size="sm"
            variant={isActiveRewrite ? "default" : "outline"}
            className="h-7 rounded-full px-2 text-[10px]"
            onClick={() => data.onActivateRewrite(node.id)}
          >
            {isActiveRewrite ? "Active" : "Use branch"}
          </Button>
        ) : (
          <GripIcon className="mt-1 size-3.5 text-stone-500" />
        )}
      </div>
      <input
        value={node.title}
        onChange={(event) => data.onChange(node.id, { title: event.target.value })}
        className="mb-2 w-full border-0 bg-transparent p-0 text-sm font-semibold text-stone-900 outline-none placeholder:text-stone-400"
        placeholder={`${NODE_LABELS[node.kind]} title`}
      />
      <Handle type="target" position={Position.Top} className="!border-stone-500/30 !bg-white" />
      <Handle type="source" position={Position.Bottom} className="!border-stone-500/30 !bg-white" />
      <GraphNodeEditor
        value={node.content}
        placeholder={getDefaultNodeContent(node.kind)}
        onChange={(value) => data.onChange(node.id, { content: value })}
        className="border-white/80 bg-white/80"
      />
    </div>
  );
});

const NODE_TYPES = {
  sectionFrame: SectionFrameNode,
  editorialNode: EditorialNode,
};

export function GraphComposerShell({
  document,
  onOpenCollage,
}: {
  document: DocumentRecord;
  onOpenCollage?: () => void;
}) {
  const updateDocument = useUpdateDocument(document.doc_id);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const envelopeRef = useRef<ComposerStateEnvelope>(normalizeComposerState(document.editor_json));
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [title, setTitle] = useState(document.title);
  const [writingMemory, setWritingMemory] = useState(document.writing_memory ?? "");
  const [saveState, setSaveState] = useState<"saved" | "dirty" | "saving">("saved");
  const [edgeKind, setEdgeKind] = useState<GraphEdgeKind>("references");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [focusedSectionId, setFocusedSectionId] = useState<string | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [sourceFilter, setSourceFilter] = useState<"all" | BlockSource>("all");
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance | null>(null);
  const [envelope, setEnvelope] = useState<ComposerStateEnvelope>(() => normalizeComposerState(document.editor_json));
  const [graph, setGraph] = useState<GraphComposerDocument>(() => {
    const normalized = normalizeComposerState(document.editor_json);
    return normalized.graph_composer ?? seedGraphFromMarkdown(document.content_markdown);
  });
  const [blocks, setBlocks] = useState(() => loadBlocks(document.doc_id));

  useEffect(() => {
    const normalized = normalizeComposerState(document.editor_json);
    setEnvelope(normalized);
    envelopeRef.current = normalized;
    setTitle(document.title);
    setWritingMemory(document.writing_memory ?? "");
    setGraph(normalized.graph_composer ?? seedGraphFromMarkdown(document.content_markdown));
    setFocusedSectionId(null);
    setSaveState("saved");
  }, [document.content_markdown, document.doc_id, document.editor_json, document.title, document.writing_memory]);

  useEffect(() => {
    envelopeRef.current = envelope;
  }, [envelope]);

  useEffect(() => {
    const refresh = () => setBlocks(loadBlocks(document.doc_id));
    refresh();
    const id = setInterval(refresh, 2500);
    return () => clearInterval(id);
  }, [document.doc_id]);

  useEffect(() => {
    const element = canvasRef.current;
    if (!element) {
      return;
    }
    const updateSize = () => {
      const rect = element.getBoundingClientRect();
      const nextWidth = Math.round(rect.width);
      const nextHeight = Math.round(rect.height);
      setCanvasSize((current) => (
        current.width === nextWidth && current.height === nextHeight
          ? current
          : { width: nextWidth, height: nextHeight }
      ));
    };
    updateSize();
    const frameId = window.requestAnimationFrame(updateSize);
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      updateSize();
    });
    observer.observe(element);
    return () => {
      window.cancelAnimationFrame(frameId);
      observer.disconnect();
    };
  }, []);

  const compiled = useMemo(() => compileGraphDocument(graph), [graph]);
  const graphIsStale = useMemo(
    () => isGraphStaleAgainstMarkdown(envelope.graph_composer, document.content_markdown),
    [document.content_markdown, envelope.graph_composer],
  );
  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [graph.nodes, selectedNodeId],
  );
  const sourceCounts = useMemo(() => {
    return blocks.reduce<Record<string, number>>((acc, block) => {
      acc[block.source] = (acc[block.source] ?? 0) + 1;
      return acc;
    }, {});
  }, [blocks]);
  const importedSourceCounts = useMemo(() => {
    return graph.nodes.reduce<Record<string, number>>((acc, node) => {
      if (node.kind === "source" && node.source) {
        acc[node.source] = (acc[node.source] ?? 0) + 1;
      }
      return acc;
    }, {});
  }, [graph.nodes]);
  const filteredBlocks = useMemo(() => (
    blocks
      .filter((block) => sourceFilter === "all" || block.source === sourceFilter)
      .sort((left, right) => right.addedAt - left.addedAt)
  ), [blocks, sourceFilter]);
  const hasMeasuredCanvas = canvasSize.width > 0 && canvasSize.height > 0;
  const sortedSections = useMemo(
    () => [...graph.section_frames].sort((left, right) => left.position.x - right.position.x || left.position.y - right.position.y),
    [graph.section_frames],
  );
  const activeSectionId = useMemo(() => {
    const selectedNode = graph.nodes.find((node) => node.id === selectedNodeId);
    return selectedNode?.sectionId ?? focusedSectionId ?? sortedSections[0]?.id ?? null;
  }, [focusedSectionId, graph.nodes, selectedNodeId, sortedSections]);

  useEffect(() => {
    setSaveState("dirty");
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    saveTimeoutRef.current = setTimeout(() => {
      setSaveState("saving");
      const nextGraph: GraphComposerDocument = {
        ...graph,
        last_compiled_hash: hashString(compiled.markdown),
        last_compiled_at: new Date().toISOString(),
      };
      const nextEnvelope = withGraphComposer(envelopeRef.current, nextGraph);
      updateDocument.mutateAsync({
        title: title.trim() || "Untitled piece",
        content_markdown: compiled.markdown,
        editor_json: nextEnvelope,
        writing_memory: writingMemory,
        status: "active",
      })
        .then((updated) => {
          setEnvelope(normalizeComposerState(updated.editor_json));
          setSaveState("saved");
        })
        .catch((error) => {
          setSaveState("dirty");
          toast.error(error instanceof Error ? error.message : String(error));
        });
    }, 1200);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [compiled.markdown, graph, title, updateDocument, writingMemory]);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (saveState === "saved") {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [saveState]);

  const mutateGraph = useCallback((mutator: (current: GraphComposerDocument) => GraphComposerDocument) => {
    setGraph((current) => {
      const next = mutator(current);
      return {
        ...next,
        section_frames: next.section_frames.map((frame) => ({
          ...frame,
          height: frameHeightFor(frame.id, next.nodes),
        })),
      };
    });
  }, []);

  // useCallback-wrapped handlers to prevent unnecessary re-renders of child components
  const handleAddSection = useCallback(() => {
    mutateGraph((current) => {
      const nextIndex = current.section_frames.length + 1;
      const frameId = nextId("section");
      return {
        ...current,
        section_frames: [
          ...current.section_frames,
          {
            id: frameId,
            title: `Section ${nextIndex}`,
            position: { x: current.section_frames.length * 420, y: 0 },
            width: 380,
            height: 860,
          },
        ],
      };
    });
  }, [mutateGraph]);

  const handleAddNode = useCallback((kind: GraphNodeKind, sectionId?: string | null) => {
    mutateGraph((current) => {
      const selectedNode = current.nodes.find((node) => node.id === selectedNodeId);
      const targetSection = current.section_frames.find((frame) => frame.id === (sectionId ?? selectedNode?.sectionId))
        ?? current.section_frames[0];
      const sectionNodeCount = current.nodes.filter((node) => node.sectionId === targetSection?.id).length;
      const nodeId = nextId("node");
      const nextNode: GraphComposerNode = {
        id: nodeId,
        kind,
        title: kind === "section" ? `Section ${current.section_frames.length + 1}` : NODE_LABELS[kind],
        content: getDefaultNodeContent(kind),
        position: {
          x: (targetSection?.position.x ?? 0) + 22,
          y: 96 + (sectionNodeCount * 148),
        },
        sectionId: targetSection?.id ?? null,
        source: kind === "source" ? "manual" : null,
      };
      return {
        ...current,
        nodes: [...current.nodes, nextNode],
      };
    });
  }, [mutateGraph, selectedNodeId]);

  const handleImportBlock = useCallback((blockId: string) => {
    const block = blocks.find((candidate) => candidate.id === blockId);
    if (!block) {
      return;
    }
    mutateGraph((current) => {
      const targetSection = current.section_frames[0];
      const nodeCount = current.nodes.filter((node) => node.sectionId === targetSection?.id).length;
      const sourceNode = convertBlockToSourceNode(block, targetSection?.id ?? null, nodeCount);
      sourceNode.position = {
        x: (targetSection?.position.x ?? 0) + 22,
        y: 96 + (nodeCount * 148),
      };
      return {
        ...current,
        nodes: [...current.nodes, sourceNode],
      };
    });
    toast.success("Imported into graph");
  }, [mutateGraph, blocks]);

  const handleImportAllFromSource = useCallback((source: BlockSource) => {
    const alreadyImported = new Set(
      graph.nodes
        .filter((node) => node.kind === "source" && node.source === source)
        .map((node) => node.title),
    );
    const matching = blocks.filter((block) => block.source === source && !alreadyImported.has(block.title));
    if (matching.length === 0) {
      toast.message(`No new ${source} clips to import`);
      return;
    }
    mutateGraph((current) => {
      const targetSection = current.section_frames[0];
      const existingCount = current.nodes.filter((node) => node.sectionId === targetSection?.id).length;
      const importedNodes = matching.map((block, index) => {
        const node = convertBlockToSourceNode(block, targetSection?.id ?? null, existingCount + index);
        node.position = {
          x: (targetSection?.position.x ?? 0) + 22,
          y: 96 + ((existingCount + index) * 148),
        };
        return node;
      });
      return {
        ...current,
        nodes: [...current.nodes, ...importedNodes],
      };
    });
    toast.success(`Imported ${matching.length} ${source} clip${matching.length === 1 ? "" : "s"}`);
  }, [mutateGraph, graph.nodes, blocks]);

  const handleAddStarterPattern = useCallback((pattern: "claim-evidence" | "quote-turn" | "rewrite-branch") => {
    mutateGraph((current) => {
      const targetSection = current.section_frames[0];
      const sectionNodes = current.nodes.filter((node) => node.sectionId === targetSection?.id).length;
      const baseY = 96 + (sectionNodes * 148);
      const additions: GraphComposerNode[] = [];
      if (pattern === "claim-evidence") {
        additions.push(
          {
            id: nextId("node"),
            kind: "paragraph",
            title: "Claim",
            content: "State the central point clearly and concretely.",
            position: { x: (targetSection?.position.x ?? 0) + 22, y: baseY },
            sectionId: targetSection?.id ?? null,
            source: null,
          },
          {
            id: nextId("node"),
            kind: "evidence",
            title: "Evidence",
            content: "- Add a grounded fact\n- Add a concrete example",
            position: { x: (targetSection?.position.x ?? 0) + 22, y: baseY + 148 },
            sectionId: targetSection?.id ?? null,
            source: null,
          },
        );
      } else if (pattern === "quote-turn") {
        additions.push(
          {
            id: nextId("node"),
            kind: "quote",
            title: "Quote",
            content: "Drop in a sourced line or excerpt here.",
            position: { x: (targetSection?.position.x ?? 0) + 22, y: baseY },
            sectionId: targetSection?.id ?? null,
            source: null,
          },
          {
            id: nextId("node"),
            kind: "transition",
            title: "Turn",
            content: "Explain what the quote changes, proves, or complicates.",
            position: { x: (targetSection?.position.x ?? 0) + 22, y: baseY + 148 },
            sectionId: targetSection?.id ?? null,
            source: null,
          },
        );
      } else {
        const anchorId = selectedNode?.id ?? null;
        const rewriteNode: GraphComposerNode = {
          id: nextId("node"),
          kind: "rewrite",
          title: "Alternate branch",
          content: "Write a sharper alternate version of the selected idea.",
          position: { x: (targetSection?.position.x ?? 0) + 32, y: baseY },
          sectionId: targetSection?.id ?? null,
          source: null,
        };
        additions.push(rewriteNode);
        return {
          ...current,
          nodes: [...current.nodes, ...additions],
          edges: anchorId
            ? [...current.edges, { id: nextId("edge"), source: anchorId, target: rewriteNode.id, kind: "rewrite-of" }]
            : current.edges,
        };
      }
      return {
        ...current,
        nodes: [...current.nodes, ...additions],
      };
    });
  }, [mutateGraph, selectedNode?.id]);

  const handleConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target) {
      return;
    }
    mutateGraph((current) => ({
      ...current,
      edges: [
        ...current.edges,
        {
          id: nextId("edge"),
          source: connection.source,
          target: connection.target,
          kind: edgeKind,
        } satisfies GraphComposerEdge,
      ],
    }));
  }, [mutateGraph, edgeKind]);

  const handleFocusSection = useCallback((sectionId: string) => {
    setSelectedNodeId(null);
    setFocusedSectionId(sectionId);
    const section = graph.section_frames.find((frame) => frame.id === sectionId);
    if (!section || !flowInstance) {
      return;
    }
    void flowInstance.setCenter(
      section.position.x + section.width / 2,
      section.position.y + section.height / 2,
      { zoom: 0.72, duration: 500 },
    );
  }, [flowInstance, graph.section_frames]);

  const handleSetEdgeKind = useCallback((kind: GraphEdgeKind) => {
    setEdgeKind(kind);
  }, []);

  const handleSetSourceFilter = useCallback((filter: "all" | BlockSource) => {
    setSourceFilter(filter);
  }, []);

  const updateNode = useCallback((nodeId: string, patch: Partial<GraphComposerNode>) => {
    mutateGraph((current) => ({
      ...current,
      nodes: current.nodes.map((node) => node.id === nodeId ? { ...node, ...patch } : node),
    }));
  }, [mutateGraph]);

  const activateRewrite = useCallback((nodeId: string) => {
    mutateGraph((current) => ({
      ...current,
      active_rewrite_node_ids: [nodeId],
    }));
  }, [mutateGraph]);

  const duplicateSelectedNode = useCallback(() => {
    if (!selectedNode) {
      return;
    }
    mutateGraph((current) => ({
      ...current,
      nodes: [
        ...current.nodes,
        {
          ...selectedNode,
          id: nextId("node"),
          title: `${selectedNode.title} copy`,
          position: { x: selectedNode.position.x + 24, y: selectedNode.position.y + 32 },
        },
      ],
    }));
  }, [mutateGraph, selectedNode]);

  const deleteSelectedNode = useCallback(() => {
    if (!selectedNode) {
      return;
    }
    mutateGraph((current) => ({
      ...current,
      nodes: current.nodes.filter((node) => node.id !== selectedNode.id),
      edges: current.edges.filter((edge) => edge.source !== selectedNode.id && edge.target !== selectedNode.id),
      active_rewrite_node_ids: current.active_rewrite_node_ids.filter((id) => id !== selectedNode.id),
    }));
    setSelectedNodeId(null);
  }, [mutateGraph, selectedNode]);

  const convertSelectedNode = useCallback((kind: GraphNodeKind) => {
    if (!selectedNode) {
      return;
    }
    updateNode(selectedNode.id, { kind, title: NODE_LABELS[kind] });
  }, [selectedNode, updateNode]);

  const createRewriteFromSelected = useCallback(() => {
    if (!selectedNode || selectedNode.kind === "rewrite") {
      return;
    }
    mutateGraph((current) => {
      const rewriteId = nextId("node");
      const rewriteNode: GraphComposerNode = {
        id: rewriteId,
        kind: "rewrite",
        title: `${selectedNode.title || "Selected card"} rewrite`,
        content: selectedNode.content,
        position: { x: selectedNode.position.x + 304, y: selectedNode.position.y + 8 },
        sectionId: selectedNode.sectionId,
        source: null,
      };
      return {
        ...current,
        nodes: [...current.nodes, rewriteNode],
        edges: [
          ...current.edges,
          {
            id: nextId("edge"),
            source: selectedNode.id,
            target: rewriteId,
            kind: "rewrite-of",
          },
        ],
      };
    });
  }, [mutateGraph, selectedNode]);

  const focusNode = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
    const node = graph.nodes.find((candidate) => candidate.id === nodeId);
    if (!node || !flowInstance) {
      return;
    }
    void flowInstance.setCenter(node.position.x + 135, node.position.y + 90, {
      zoom: 1.05,
      duration: 500,
    });
  }, [flowInstance, graph.nodes]);

  function rebuildFromDocument() {
    const rebuilt = seedGraphFromMarkdown(document.content_markdown);
    setGraph(rebuilt);
    toast.success("Graph rebuilt from the latest linear draft");
  }

  async function handleManualSave() {
    try {
      setSaveState("saving");
      const nextGraph = {
        ...graph,
        last_compiled_hash: hashString(compiled.markdown),
        last_compiled_at: new Date().toISOString(),
      };
      const nextEnvelope = withGraphComposer(envelopeRef.current, nextGraph);
      const updated = await updateDocument.mutateAsync({
        title: title.trim() || "Untitled piece",
        content_markdown: compiled.markdown,
        editor_json: nextEnvelope,
        writing_memory: writingMemory,
        status: "active",
      });
      setEnvelope(normalizeComposerState(updated.editor_json));
      setSaveState("saved");
      toast.success("Graph draft saved");
    } catch (error) {
      setSaveState("dirty");
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  const rfNodes = useMemo<Node[]>(() => {
    const frames: Node[] = graph.section_frames.map((frame) => ({
      id: frame.id,
      type: "sectionFrame",
      position: frame.position,
      draggable: true,
      selectable: true,
      data: {
        frame,
        count: graph.nodes.filter((node) => node.sectionId === frame.id).length,
      },
      style: {
        width: frame.width,
        height: frame.height,
      },
    }));

    const cards: Node[] = graph.nodes.map((node) => ({
      id: node.id,
      type: "editorialNode",
      position: node.position,
      data: {
        node,
        activeRewriteIds: graph.active_rewrite_node_ids,
        onChange: updateNode,
        onActivateRewrite: activateRewrite,
      },
      draggable: true,
      selectable: true,
    }));
    return [...frames, ...cards];
  }, [activateRewrite, graph, updateNode]);

  const rfEdges = useMemo<Edge[]>(
    () => graph.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.kind,
      animated: edge.kind === "rewrite-of",
      style: {
        stroke: EDGE_COLORS[edge.kind],
        strokeWidth: edge.kind === "rewrite-of" ? 2.75 : 2.1,
      },
      labelStyle: {
        fontSize: 11,
        fill: EDGE_COLORS[edge.kind],
      },
    })),
    [graph.edges],
  );

  function handleNodesChange(changes: NodeChange[]) {
    mutateGraph((current) => {
      let next = current;
      for (const change of changes) {
        if (change.type !== "position" || !change.position) {
          continue;
        }
        const nextPosition = change.position;
        if (current.section_frames.some((frame) => frame.id === change.id)) {
          const previous = current.section_frames.find((frame) => frame.id === change.id);
          if (!previous) {
            continue;
          }
          const deltaX = nextPosition.x - previous.position.x;
          const deltaY = nextPosition.y - previous.position.y;
          next = {
            ...next,
            section_frames: next.section_frames.map((frame) => frame.id === change.id
              ? { ...frame, position: nextPosition }
              : frame),
            nodes: next.nodes.map((node) => node.sectionId === change.id
              ? {
                ...node,
                position: {
                  x: node.position.x + deltaX,
                  y: node.position.y + deltaY,
                },
              }
              : node),
          };
          continue;
        }

        next = {
          ...next,
          nodes: next.nodes.map((node) => {
            if (node.id !== change.id) {
              return node;
            }
            const center = { x: nextPosition.x + 135, y: nextPosition.y + 90 };
            const containingFrame = next.section_frames.find((frame) => pointInsideFrame(center, frame));
            return {
              ...node,
              position: nextPosition,
              sectionId: containingFrame?.id ?? node.sectionId,
            };
          }),
        };
      }
      return next;
    });
  }

  return (
    <div className="grid size-full min-h-0 grid-cols-1 gap-4 xl:grid-cols-[16rem_minmax(24rem,1fr)_20rem] 2xl:grid-cols-[18rem_minmax(32rem,1fr)_24rem]">
      <Card className="min-h-0 min-w-0 overflow-hidden border-stone-700/10 bg-[linear-gradient(180deg,rgba(255,251,235,0.92),rgba(255,248,240,0.9))] py-4 shadow-[0_18px_50px_rgba(120,53,15,0.08)]">
        <CardHeader className="px-4">
          <div className="text-[11px] uppercase tracking-[0.24em] text-stone-500">Patchbay Writer</div>
          <CardTitle className="flex items-center gap-2 text-stone-950">
            <FolderTreeIcon className="size-4" />
            Graph Composer
          </CardTitle>
          <CardDescription className="text-stone-600">
            Build the draft as connected editorial cards, then let the manuscript compile on the right.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex h-full min-h-0 flex-col gap-4 px-4">
                <div className="space-y-3">
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="w-full rounded-xl border border-stone-700/15 bg-white/80 px-3 py-2 text-sm font-semibold text-stone-900 outline-none placeholder:text-stone-400"
              placeholder="Piece title"
            />
                  <div className="flex flex-wrap gap-2">
              <Badge variant="outline" className="border-stone-400/30 bg-white/70 text-stone-600">
                {graph.nodes.length} cards
              </Badge>
              <Badge variant="outline" className="border-stone-400/30 bg-white/70 text-stone-600">
                {compiled.plainText.trim() ? compiled.plainText.trim().split(/\s+/).length : 0} words
              </Badge>
              <LifecyclePill
                tone={saveState === "saving" ? "working" : saveState === "dirty" ? "idle" : "success"}
                label={saveState === "saving" ? "Saving" : saveState === "dirty" ? "Draft changed" : "Saved"}
                detail={saveState === "saving" ? "autosyncing manuscript" : saveState === "dirty" ? "manual or autosave pending" : "graph and markdown aligned"}
              />
            </div>
          </div>

          <div className="space-y-2 rounded-2xl border border-stone-700/10 bg-white/70 p-3">
            <div className="text-[11px] uppercase tracking-[0.22em] text-stone-500">Structure</div>
            <div className="space-y-1.5">
              {sortedSections.map((section, index) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => handleFocusSection(section.id)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left transition",
                    activeSectionId === section.id
                      ? "border-stone-900/20 bg-white shadow-sm"
                      : "border-stone-700/10 bg-white/80 hover:border-stone-700/20",
                  )}
                >
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.16em] text-stone-500">Section {index + 1}</div>
                    <div className="text-sm font-medium text-stone-900">{section.title}</div>
                  </div>
                  <Badge variant="outline" className="bg-white/80 text-[10px]">
                    {graph.nodes.filter((node) => node.sectionId === section.id).length}
                  </Badge>
                </button>
              ))}
            </div>
          </div>

          {graphIsStale ? (
            <div className="rounded-2xl border border-amber-500/30 bg-amber-50/90 p-3 text-xs text-amber-900">
              <div className="font-medium">Linear draft changed after the last graph compile.</div>
              <div className="mt-1 text-amber-800/80">
                Rebuild the graph from the latest document or keep the saved graph and continue comparing.
              </div>
              <div className="mt-2 flex gap-2">
                <Button size="sm" className="h-7 rounded-full text-xs" onClick={rebuildFromDocument}>
                  <RefreshCwIcon className="size-3.5" />
                  Rebuild graph
                </Button>
                <Button size="sm" variant="outline" className="h-7 rounded-full text-xs" onClick={() => toast.message("Keeping saved graph")}>
                  <GitCompareArrowsIcon className="size-3.5" />
                  Keep saved graph
                </Button>
              </div>
            </div>
          ) : null}

          <div className="space-y-2">
            <div className="text-[11px] uppercase tracking-[0.22em] text-stone-500">Node Palette</div>
            <div className="grid grid-cols-2 gap-2">
              {(["paragraph", "evidence", "quote", "transition", "note", "rewrite"] as GraphNodeKind[]).map((kind) => (
                <Button
                  key={kind}
                  size="sm"
                  variant="outline"
                  className="justify-start rounded-xl border-stone-700/15 bg-white/70 text-xs text-stone-700"
                  onClick={() => handleAddNode(kind)}
                >
                  <PlusIcon className="size-3.5" />
                  {NODE_LABELS[kind]}
                </Button>
              ))}
            </div>
            <Button
              size="sm"
              variant="secondary"
              className="w-full justify-start rounded-xl text-xs"
              onClick={handleAddSection}
            >
              <MilestoneIcon className="size-3.5" />
              Add section frame
            </Button>
          </div>

                <div className="space-y-2">
            <div className="text-[11px] uppercase tracking-[0.22em] text-stone-500">Starter Patterns</div>
            <div className="grid grid-cols-1 gap-2">
              <Button size="sm" variant="outline" className="justify-start rounded-xl border-stone-700/15 bg-white/70 text-xs text-stone-700" onClick={() => handleAddStarterPattern("claim-evidence")}>
                <BookMarkedIcon className="size-3.5" />
                Claim + evidence
              </Button>
              <Button size="sm" variant="outline" className="justify-start rounded-xl border-stone-700/15 bg-white/70 text-xs text-stone-700" onClick={() => handleAddStarterPattern("quote-turn")}>
                <ScrollTextIcon className="size-3.5" />
                Quote + turn
              </Button>
              <Button size="sm" variant="outline" className="justify-start rounded-xl border-stone-700/15 bg-white/70 text-xs text-stone-700" onClick={() => handleAddStarterPattern("rewrite-branch")}>
                <ArrowRightLeftIcon className="size-3.5" />
                Rewrite branch
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-[11px] uppercase tracking-[0.22em] text-stone-500">Connection Mode</div>
            <div className="grid grid-cols-2 gap-2">
              {(["references", "supports", "contradicts", "rewrite-of"] as GraphEdgeKind[]).map((kind) => (
                <Button
                  key={kind}
                  size="sm"
                  variant={edgeKind === kind ? "default" : "outline"}
                  className="rounded-xl text-xs"
                  onClick={() => handleSetEdgeKind(kind)}
                >
                  <SplinePointerIcon className="size-3.5" />
                  {kind}
                </Button>
              ))}
            </div>
          </div>

          <div className="min-h-0 flex-1">
            <div className="mb-2 flex items-center justify-between">
              <div className="text-[11px] uppercase tracking-[0.22em] text-stone-500">Import From Blocks</div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="border-stone-400/30 bg-white/70 text-stone-600">
                  {blocks.length}
                </Badge>
                {onOpenCollage ? (
                  <Button size="sm" variant="ghost" className="h-7 rounded-full px-2 text-[10px]" onClick={onOpenCollage}>
                    <PanelLeftOpenIcon className="size-3.5" />
                    Open Collage
                  </Button>
                ) : null}
              </div>
            </div>
            <div className="grid grid-cols-1 gap-2">
              <div className="rounded-2xl border border-stone-700/10 bg-white/70 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="text-xs font-semibold text-stone-900">Working knowledge intake</div>
                    <div className="mt-1 text-[11px] leading-5 text-stone-600">
                      Calibre and Pinboard clips land in Collage first, then come into the graph as source cards.
                    </div>
                  </div>
                  <MousePointerClickIcon className="size-4 text-stone-500" />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {(["calibre", "pinboard"] as BlockSource[]).map((source) => (
                    <button
                      key={source}
                      type="button"
                      className="rounded-2xl border border-stone-700/10 bg-white px-3 py-2 text-left transition hover:-translate-y-0.5 hover:border-stone-700/20"
                      onClick={() => handleImportAllFromSource(source)}
                      disabled={!sourceCounts[source]}
                    >
                      <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500">{SOURCE_DISPLAY_LABEL[source]}</div>
                      <div className="mt-1 text-lg font-semibold text-stone-900">{sourceCounts[source] ?? 0}</div>
                      <div className="mt-1 text-[11px] text-stone-600">
                        {importedSourceCounts[source] ?? 0} already on canvas
                      </div>
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Button
                  size="sm"
                  variant={sourceFilter === "all" ? "default" : "outline"}
                  className="h-7 rounded-full px-2.5 text-[10px]"
                  onClick={() => handleSetSourceFilter("all")}
                >
                  all · {blocks.length}
                </Button>
                {SOURCE_PRIORITY.map((source) => (
                  <Button
                    key={source}
                    size="sm"
                    variant={sourceFilter === source ? "default" : "outline"}
                    className="h-7 rounded-full px-2.5 text-[10px]"
                    onClick={() => handleSetSourceFilter(source)}
                    disabled={!sourceCounts[source]}
                  >
                    {source} · {sourceCounts[source] ?? 0}
                  </Button>
                ))}
              </div>
            </div>
            <ScrollArea className="h-[16rem] pr-2">
              <div className="space-y-2">
                {blocks.length === 0 ? (
                  <div className="pointer-events-none rounded-2xl border border-dashed border-stone-700/15 bg-white/55 p-3 text-xs text-stone-500">
                    No Collage blocks yet. Switch to Collage to collect source material first.
                  </div>
                ) : (
                  filteredBlocks.map((block) => (
                    <button
                      key={block.id}
                      type="button"
                      className="w-full rounded-2xl border border-stone-700/10 bg-white/70 p-3 text-left transition hover:-translate-y-0.5 hover:bg-white"
                      onClick={() => handleImportBlock(block.id)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <div className="text-xs font-medium text-stone-900">{block.title}</div>
                            <Badge variant="outline" className={cn("bg-white/80 text-[10px]", SOURCE_BADGES[block.source])}>
                              {block.source}
                            </Badge>
                          </div>
                          <div className="mt-1 line-clamp-2 text-[11px] leading-5 text-stone-600">{block.content}</div>
                        </div>
                        <FileSymlinkIcon className="mt-0.5 size-3.5 shrink-0 text-stone-500" />
                      </div>
                    </button>
                  ))
                )}
              </div>
            </ScrollArea>
          </div>

          <div className="space-y-2 rounded-2xl border border-stone-700/10 bg-white/70 p-3">
            <div className="text-[11px] uppercase tracking-[0.22em] text-stone-500">Selected Card</div>
            {selectedNode ? (
              <>
                <div className="text-sm font-semibold text-stone-900">{selectedNode.title || NODE_LABELS[selectedNode.kind]}</div>
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant="outline" className="bg-white/80">{NODE_LABELS[selectedNode.kind]}</Badge>
                  {selectedNode.source ? <Badge variant="outline" className={cn("bg-white/80", SOURCE_BADGES[selectedNode.source])}>{selectedNode.source}</Badge> : null}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Button size="sm" variant="outline" className="rounded-xl text-xs" onClick={duplicateSelectedNode}>
                    Duplicate
                  </Button>
                  <Button size="sm" variant="outline" className="rounded-xl text-xs" onClick={deleteSelectedNode}>
                    <Trash2Icon className="size-3.5" />
                    Remove
                  </Button>
                  <Button size="sm" variant="outline" className="rounded-xl text-xs" onClick={() => convertSelectedNode("paragraph")}>
                    Paragraph
                  </Button>
                  <Button size="sm" variant="outline" className="rounded-xl text-xs" onClick={() => convertSelectedNode("evidence")}>
                    Evidence
                  </Button>
                  <Button size="sm" variant="outline" className="rounded-xl text-xs" onClick={() => convertSelectedNode("quote")}>
                    Quote
                  </Button>
                  <Button size="sm" variant="outline" className="rounded-xl text-xs" onClick={() => convertSelectedNode("rewrite")}>
                    Rewrite
                  </Button>
                  {selectedNode.kind === "rewrite" ? (
                    <Button size="sm" variant="default" className="rounded-xl text-xs" onClick={() => activateRewrite(selectedNode.id)}>
                      Make active
                    </Button>
                  ) : (
                    <Button size="sm" variant="secondary" className="rounded-xl text-xs" onClick={createRewriteFromSelected}>
                      Create rewrite
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <div className="text-xs text-stone-500">
                Select any card on the canvas or in the preview to duplicate it, convert it, or mark a rewrite branch active.
              </div>
            )}
          </div>

          <Button size="sm" className="rounded-xl" onClick={() => void handleManualSave()} disabled={updateDocument.isPending}>
            {updateDocument.isPending ? <Loader2Icon className="size-3.5 animate-spin" /> : <SaveIcon className="size-3.5" />}
            Save graph draft
          </Button>
        </CardContent>
      </Card>

      <Card className="min-h-0 min-w-0 overflow-hidden border-stone-700/10 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.16),transparent_24%),linear-gradient(180deg,rgba(255,251,235,0.95),rgba(245,245,244,0.94))] py-4 shadow-[0_24px_80px_rgba(120,53,15,0.08)]">
        <CardHeader className="px-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-stone-500">Editorial Canvas</div>
              <CardTitle className="flex items-center gap-2 text-stone-950">
                <BookMarkedIcon className="size-4" />
                Section Graph
              </CardTitle>
              <CardDescription className="text-stone-600">
                Arrange cards spatially. Section order is left-to-right; card order is top-to-bottom inside a section.
              </CardDescription>
            </div>
            <Badge variant="outline" className="border-stone-400/30 bg-white/70 text-stone-600">
              {edgeKind} mode
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="h-full min-h-0 px-4 pb-4">
          <div
            ref={canvasRef}
            className="h-[calc(100vh-19rem)] min-h-[40rem] overflow-hidden rounded-[26px] border border-stone-700/10 bg-white/65"
          >
            {hasMeasuredCanvas ? (
            <div className="size-full" style={{ width: canvasSize.width, height: canvasSize.height }}>
              <ReactFlow
                key={`${canvasSize.width}x${canvasSize.height}`}
                nodes={rfNodes}
                edges={rfEdges}
                nodeTypes={NODE_TYPES}
                onNodesChange={handleNodesChange}
                onConnect={handleConnect}
                onNodeClick={(_event, node) => setSelectedNodeId(node.id)}
                onInit={setFlowInstance}
                fitView
                fitViewOptions={{ padding: 0.12 }}
                className="h-full w-full bg-transparent"
                style={{ width: canvasSize.width, height: canvasSize.height }}
                defaultEdgeOptions={{ type: "smoothstep" }}
                minZoom={0.4}
                maxZoom={1.6}
                proOptions={{ hideAttribution: true }}
              >
                <Background variant={BackgroundVariant.Dots} gap={22} size={1} className="opacity-35" />
                <MiniMap pannable zoomable className="rounded-2xl border border-stone-700/10 bg-white/90" />
                <Controls className="rounded-2xl border border-stone-700/10 bg-white/90 shadow-sm" />
              </ReactFlow>
            </div>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-stone-500">
                Preparing graph canvas…
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="min-h-0 min-w-0 overflow-hidden border-stone-700/10 bg-[linear-gradient(180deg,rgba(250,250,249,0.97),rgba(245,245,244,0.96))] py-4 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
        <CardHeader className="px-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-stone-500">Compiled Reading</div>
              <CardTitle className="flex items-center gap-2 text-stone-950">
                <ScrollTextIcon className="size-4" />
                Manuscript Preview
              </CardTitle>
              <CardDescription className="text-stone-600">
                This is the linear draft generated from the current graph state.
              </CardDescription>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="rounded-full"
              onClick={() => {
                const blob = new Blob([compiled.markdown], { type: "text/markdown;charset=utf-8" });
                const url = URL.createObjectURL(blob);
                const anchor = window.document.createElement("a");
                anchor.href = url;
                anchor.download = `${title.trim() || "graph-draft"}.md`;
                anchor.click();
                URL.revokeObjectURL(url);
              }}
            >
              <FileDownIcon className="size-3.5" />
              Download
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex h-full min-h-0 flex-col gap-4 px-4">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{compiled.segments.length} segments</Badge>
            <Badge variant="outline">{compiled.plainText.trim() ? compiled.plainText.trim().split(/\s+/).length : 0} words</Badge>
            <Badge variant="outline">{graph.active_rewrite_node_ids.length} active rewrites</Badge>
          </div>
          <ScrollArea className="h-[calc(100vh-21rem)] min-h-[40rem] pr-3">
            <div className="space-y-3">
              {compiled.segments.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-stone-700/15 bg-white/75 p-4 text-sm text-stone-500">
                  Add sections and cards on the canvas to build the manuscript.
                </div>
              ) : (
                compiled.segments.map((segment) => {
                  const node = graph.nodes.find((candidate) => candidate.id === segment.nodeId);
                  const section = node?.sectionId
                    ? graph.section_frames.find((frame) => frame.id === node.sectionId)
                    : null;
                  return (
                  <button
                    key={segment.nodeId}
                    type="button"
                    onClick={() => focusNode(segment.nodeId)}
                    className={cn(
                      "w-full rounded-2xl border p-4 text-left transition-all",
                      selectedNodeId === segment.nodeId
                        ? "border-stone-900/20 bg-white shadow-sm"
                        : "border-stone-700/10 bg-white/80 hover:border-stone-700/20",
                    )}
                  >
                    <div className="mb-2 flex items-center justify-between gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500">
                      <div className="flex items-center gap-2">
                      <ArrowRightLeftIcon className="size-3.5" />
                        <span>{node?.title ?? "Source card"}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {section ? (
                          <Badge variant="outline" className="bg-white/70 text-[10px]">
                            {section.title}
                          </Badge>
                        ) : null}
                        <Badge variant="outline" className="bg-white/70 text-[10px]">
                          {NODE_LABELS[node?.kind ?? "paragraph"]}
                        </Badge>
                        {node?.source ? (
                          <Badge variant="outline" className={cn("bg-white/70 text-[10px]", SOURCE_BADGES[node.source])}>
                            {node.source}
                          </Badge>
                        ) : null}
                      </div>
                    </div>
                    <div className="whitespace-pre-wrap text-sm leading-7 text-stone-800">{segment.markdown}</div>
                  </button>
                  );
                })
              )}
            </div>
          </ScrollArea>
          <div className="rounded-2xl border border-stone-700/10 bg-white/80 p-3 text-xs text-stone-600">
            <div className="font-medium text-stone-800">How v1 compiles</div>
            <div className="mt-1">
              Section frames control macro order. Within each section, cards compile top-to-bottom. Source cards stay visible on the graph but do not enter the manuscript until you convert or rewrite them.
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
