import type { BlockSource, CollageBlock } from "./collage-blocks";

export type ComposerMode = "editor" | "graph" | "collage";

export type GraphNodeKind =
  | "section"
  | "paragraph"
  | "evidence"
  | "quote"
  | "transition"
  | "note"
  | "source"
  | "rewrite";

export type GraphEdgeKind =
  | "supports"
  | "contradicts"
  | "references"
  | "rewrite-of";

export interface GraphPosition {
  x: number;
  y: number;
}

export interface GraphSectionFrame {
  id: string;
  title: string;
  position: GraphPosition;
  width: number;
  height: number;
}

export interface GraphComposerNode {
  id: string;
  kind: GraphNodeKind;
  title: string;
  content: string;
  position: GraphPosition;
  sectionId: string | null;
  source: BlockSource | "document" | null;
}

export interface GraphComposerEdge {
  id: string;
  kind: GraphEdgeKind;
  source: string;
  target: string;
}

export interface GraphComposerDocument {
  version: "graph-v1";
  nodes: GraphComposerNode[];
  edges: GraphComposerEdge[];
  section_frames: GraphSectionFrame[];
  active_rewrite_node_ids: string[];
  last_compiled_hash: string;
  last_compiled_at: string | null;
}

export interface ComposerStateEnvelope extends Record<string, unknown> {
  kind: "composer-state-v2";
  block_editor: Record<string, unknown> | null;
  graph_composer: GraphComposerDocument | null;
  last_active_mode: ComposerMode;
}

export interface CompiledGraphSegment {
  nodeId: string;
  markdown: string;
  plainText: string;
}

export interface CompiledGraphResult {
  markdown: string;
  plainText: string;
  segments: CompiledGraphSegment[];
}

export const DEFAULT_SECTION_FRAME: GraphSectionFrame = {
  id: "section-root",
  title: "Opening section",
  position: { x: 0, y: 0 },
  width: 380,
  height: 980,
};

export function isComposerStateEnvelope(value: unknown): value is ComposerStateEnvelope {
  return Boolean(
    value
    && typeof value === "object"
    && (value as ComposerStateEnvelope).kind === "composer-state-v2",
  );
}

export function createEmptyGraphDocument(): GraphComposerDocument {
  return {
    version: "graph-v1",
    nodes: [],
    edges: [],
    section_frames: [{ ...DEFAULT_SECTION_FRAME }],
    active_rewrite_node_ids: [],
    last_compiled_hash: "",
    last_compiled_at: null,
  };
}

export function normalizeComposerState(editorJson: Record<string, unknown> | null | undefined): ComposerStateEnvelope {
  if (isComposerStateEnvelope(editorJson)) {
    return {
      kind: "composer-state-v2",
      block_editor: editorJson.block_editor ?? null,
      graph_composer: editorJson.graph_composer ?? null,
      last_active_mode: editorJson.last_active_mode ?? "editor",
    };
  }

  return {
    kind: "composer-state-v2",
    block_editor: editorJson ?? null,
    graph_composer: null,
    last_active_mode: "editor",
  };
}

export function withBlockEditor(
  envelope: ComposerStateEnvelope,
  blockEditor: Record<string, unknown> | null,
): ComposerStateEnvelope {
  return {
    ...envelope,
    block_editor: blockEditor,
    last_active_mode: "editor",
  };
}

export function withGraphComposer(
  envelope: ComposerStateEnvelope,
  graphComposer: GraphComposerDocument | null,
): ComposerStateEnvelope {
  return {
    ...envelope,
    graph_composer: graphComposer,
    last_active_mode: "graph",
  };
}

export function withLastComposerMode(
  envelope: ComposerStateEnvelope,
  mode: ComposerMode,
): ComposerStateEnvelope {
  return {
    ...envelope,
    last_active_mode: mode,
  };
}

export function hashString(value: string): string {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) - hash) + value.charCodeAt(index);
    hash |= 0;
  }
  return String(hash);
}

function markdownForNode(node: GraphComposerNode): string {
  const content = node.content.trim();
  if (!content) {
    return "";
  }
  switch (node.kind) {
    case "section":
      return `## ${node.title.trim() || content}`;
    case "quote":
      return content
        .split("\n")
        .map((line) => `> ${line}`.trimEnd())
        .join("\n");
    case "evidence":
      return content
        .split("\n")
        .filter(Boolean)
        .map((line) => `- ${line.replace(/^-+\s*/, "")}`)
        .join("\n");
    default:
      return content;
  }
}

export function compileGraphDocument(graph: GraphComposerDocument): CompiledGraphResult {
  const sortedSections = [...graph.section_frames]
    .sort((left, right) => left.position.x - right.position.x || left.position.y - right.position.y);

  const activeRewriteIds = new Set(graph.active_rewrite_node_ids);
  const segments: CompiledGraphSegment[] = [];

  for (const section of sortedSections) {
    const nodes = graph.nodes
      .filter((node) => node.sectionId === section.id)
      .filter((node) => node.kind !== "source")
      .filter((node) => node.kind !== "rewrite" || activeRewriteIds.has(node.id))
      .sort((left, right) => left.position.y - right.position.y || left.position.x - right.position.x);

    for (const node of nodes) {
      const markdown = markdownForNode(node);
      if (!markdown) {
        continue;
      }
      segments.push({
        nodeId: node.id,
        markdown,
        plainText: node.content.trim(),
      });
    }
  }

  const markdown = segments.map((segment) => segment.markdown).join("\n\n").trim();
  return {
    markdown,
    plainText: segments.map((segment) => segment.plainText).join("\n\n").trim(),
    segments,
  };
}

export function isGraphStaleAgainstMarkdown(graph: GraphComposerDocument | null, markdown: string): boolean {
  if (!graph) {
    return false;
  }
  return graph.last_compiled_hash !== hashString(markdown.trim());
}

function nextId(prefix: string, index: number): string {
  return `${prefix}-${index + 1}`;
}

function detectNodeKind(block: string): GraphNodeKind {
  if (block.startsWith(">")) return "quote";
  if (/^[-*]\s/m.test(block)) return "evidence";
  return "paragraph";
}

export function seedGraphFromMarkdown(markdown: string): GraphComposerDocument {
  const trimmed = markdown.trim();
  const frames: GraphSectionFrame[] = [];
  const nodes: GraphComposerNode[] = [];

  const sectionRegex = /(^##\s+.+$)/gm;
  const matches = [...trimmed.matchAll(sectionRegex)];

  if (matches.length === 0) {
    frames.push({ ...DEFAULT_SECTION_FRAME, title: "Draft" });
    const blocks = trimmed
      .split(/\n{2,}/)
      .map((block) => block.trim())
      .filter(Boolean);
    blocks.forEach((block, index) => {
      nodes.push({
        id: nextId("node", index),
        kind: detectNodeKind(block),
        title: block.split("\n")[0]?.replace(/^[-#>\s]+/, "").slice(0, 48) ?? "Draft block",
        content: block.replace(/^##\s+/gm, "").trim(),
        position: { x: 18, y: 92 + (index * 132) },
        sectionId: DEFAULT_SECTION_FRAME.id,
        source: "document",
      });
    });
  } else {
    const boundaries = matches.map((match) => match.index ?? 0);
    const sections = boundaries.map((start, index) => {
      const end = boundaries[index + 1] ?? trimmed.length;
      return trimmed.slice(start, end).trim();
    });

    sections.forEach((sectionMarkdown, sectionIndex) => {
      const [headingLine = "## Untitled section", ...bodyLines] = sectionMarkdown.split("\n");
      const sectionId = `section-${sectionIndex + 1}`;
      frames.push({
        id: sectionId,
        title: headingLine.replace(/^##\s+/, "").trim(),
        position: { x: sectionIndex * 420, y: 0 },
        width: 380,
        height: 980,
      });
      bodyLines
        .join("\n")
        .split(/\n{2,}/)
        .map((block) => block.trim())
        .filter(Boolean)
        .forEach((block, blockIndex) => {
          nodes.push({
            id: `${sectionId}-node-${blockIndex + 1}`,
            kind: detectNodeKind(block),
            title: block.split("\n")[0]?.replace(/^[-#>\s]+/, "").slice(0, 48) ?? "Section block",
            content: block.trim(),
            position: { x: 18, y: 92 + (blockIndex * 132) },
            sectionId,
            source: "document",
          });
        });
    });
  }

  const graph = {
    version: "graph-v1" as const,
    nodes,
    edges: [],
    section_frames: frames.length > 0 ? frames : [{ ...DEFAULT_SECTION_FRAME }],
    active_rewrite_node_ids: [],
    last_compiled_hash: "",
    last_compiled_at: null,
  };

  const compiled = compileGraphDocument(graph);
  return {
    ...graph,
    last_compiled_hash: hashString(compiled.markdown),
    last_compiled_at: new Date().toISOString(),
  };
}

export function convertBlockToSourceNode(
  block: CollageBlock,
  sectionId: string | null,
  index: number,
): GraphComposerNode {
  return {
    id: `source-${block.id}`,
    kind: "source",
    title: block.title,
    content: block.content,
    position: { x: 18, y: 92 + (index * 132) },
    sectionId,
    source: block.source,
  };
}
