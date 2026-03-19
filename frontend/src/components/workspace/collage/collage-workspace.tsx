"use client";

import {
  ChevronDownIcon,
  ChevronRightIcon,
  DownloadIcon,
  GripVerticalIcon,
  Loader2Icon,
  PlusIcon,
  SearchIcon,
  SparklesIcon,
  XIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { getAPIClient } from "@/core/api";
import { getBackendBaseURL } from "@/core/config";
import { useTransformDocument, useUpdateDocument } from "@/core/documents/hooks";
import type { DocumentRecord } from "@/core/documents/types";
import { formatTimeAgo } from "@/core/utils/datetime";
import { cn } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────────

type BlockSource = "surfsense" | "calibre" | "chat" | "pasted" | "manual";

interface CollageBlock {
  id: string;
  source: BlockSource;
  title: string;
  content: string;
  addedAt: number;
}

export interface CollageWorkspaceProps {
  document: DocumentRecord;
  onSwitchToEditor: () => void;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const SOURCE_BORDER: Record<BlockSource, string> = {
  surfsense: "border-l-blue-500/60",
  calibre: "border-l-amber-500/60",
  chat: "border-l-violet-500/60",
  pasted: "border-l-green-500/60",
  manual: "border-l-zinc-500/60",
};

const SOURCE_BADGE: Record<BlockSource, string> = {
  surfsense: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  calibre: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  chat: "bg-violet-500/20 text-violet-400 border-violet-500/30",
  pasted: "bg-green-500/20 text-green-400 border-green-500/30",
  manual: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
};

const SOURCE_DOT: Record<BlockSource, string> = {
  surfsense: "bg-blue-400",
  calibre: "bg-amber-400",
  chat: "bg-violet-400",
  pasted: "bg-green-400",
  manual: "bg-zinc-400",
};

const SOURCE_LABELS: Record<BlockSource, string> = {
  surfsense: "SurfSense",
  calibre: "Calibre",
  chat: "Chat",
  pasted: "Pasted",
  manual: "Manual",
};

// ─── Persistence ──────────────────────────────────────────────────────────────

function loadBlocks(docId: string): CollageBlock[] {
  try {
    const raw = localStorage.getItem(`maestroflow:collage:${docId}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed as CollageBlock[];
  } catch {
    return [];
  }
}

function saveBlocks(docId: string, blocks: CollageBlock[]) {
  try {
    localStorage.setItem(`maestroflow:collage:${docId}`, JSON.stringify(blocks));
  } catch {
    // ignore quota errors
  }
}

// ─── SurfSense helpers ────────────────────────────────────────────────────────

type SSResult = { id?: number; title: string; preview?: string };

function normalizeSSResults(payload: unknown): SSResult[] {
  const candidates = [
    payload,
    (payload as { items?: unknown })?.items,
    (payload as { results?: unknown })?.results,
    (payload as { documents?: unknown })?.documents,
  ];
  const raw = candidates.find(Array.isArray) as Array<Record<string, unknown>> | undefined;
  if (!raw) return [];
  return raw.map((item) => ({
    id: typeof item.id === "number" ? item.id : undefined,
    title:
      (typeof item.title === "string" ? item.title : undefined) ??
      (typeof item.name === "string" ? item.name : undefined) ??
      "Untitled",
    preview: (
      (typeof item.preview === "string" ? item.preview : undefined) ??
      (typeof item.snippet === "string" ? item.snippet : undefined) ??
      (typeof item.source_markdown === "string" ? item.source_markdown : undefined) ??
      ""
    ).trim() || undefined,
  }));
}

// ─── Calibre helpers ──────────────────────────────────────────────────────────

type CalibreItem = { id?: number; title: string; authors?: string; preview?: string };

// ─── Thread helpers ───────────────────────────────────────────────────────────

type ThreadResult = {
  thread_id: string;
  metadata: Record<string, unknown>;
  values?: Record<string, unknown>;
};

// ─── Source badge ─────────────────────────────────────────────────────────────

function SourceBadge({ source }: { source: BlockSource }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium",
        SOURCE_BADGE[source],
      )}
    >
      <span className={cn("size-1.5 rounded-full", SOURCE_DOT[source])} />
      {SOURCE_LABELS[source]}
    </span>
  );
}

// ─── Section header ───────────────────────────────────────────────────────────

function SectionHeader({
  label,
  count,
  open,
  onToggle,
}: {
  label: string;
  count?: number;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      className="flex w-full items-center gap-1.5 py-1 text-left"
      onClick={onToggle}
    >
      {open ? (
        <ChevronDownIcon className="size-3.5 shrink-0 text-muted-foreground" />
      ) : (
        <ChevronRightIcon className="size-3.5 shrink-0 text-muted-foreground" />
      )}
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {count !== undefined && (
        <Badge variant="secondary" className="h-4 px-1 text-[10px]">
          {count}
        </Badge>
      )}
    </button>
  );
}

// ─── Left: Material Board ─────────────────────────────────────────────────────

function SurfSenseSection({ onAdd }: { onAdd: (b: Omit<CollageBlock, "id" | "addedAt">) => void }) {
  const [open, setOpen] = useState(true);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SSResult[]>([]);
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  function handleQueryChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void doSearch(value), 400);
  }

  async function doSearch(q: string) {
    if (!q.trim()) { setResults([]); return; }
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setSearching(true);
    try {
      const res = await fetch(`${getBackendBaseURL()}/api/surfsense/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
        body: JSON.stringify({ query: q.trim(), top_k: 5 }),
      });
      if (!res.ok) throw new Error(`SurfSense ${res.status}`);
      setResults(normalizeSSResults(await res.json()));
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="space-y-1.5">
      <SectionHeader label="SurfSense" count={results.length || undefined} open={open} onToggle={() => setOpen((v) => !v)} />
      {open && (
        <div className="space-y-2 pl-1">
          <div className="relative">
            <Input
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              placeholder="Search SurfSense..."
              className="h-7 pr-7 text-xs"
            />
            <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
              {searching ? (
                <Loader2Icon className="size-3 animate-spin text-muted-foreground" />
              ) : (
                <SearchIcon className="size-3 text-muted-foreground" />
              )}
            </div>
          </div>
          {results.map((item, i) => (
            <div
              key={item.id ?? i}
              className="rounded-lg border border-l-2 border-l-blue-500/50 bg-card px-2.5 py-2 text-xs"
            >
              <div className="flex items-start justify-between gap-1">
                <div className="min-w-0 font-medium leading-snug truncate">{item.title}</div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-5 shrink-0 px-1.5 text-[10px]"
                  onClick={() => {
                    onAdd({
                      source: "surfsense",
                      title: item.title,
                      content: item.preview
                        ? `> **${item.title}**\n> ${item.preview}`
                        : `> **${item.title}**`,
                    });
                    toast.success("Added to canvas");
                  }}
                >
                  <PlusIcon className="size-2.5" />
                </Button>
              </div>
              {item.preview && (
                <p className="mt-0.5 line-clamp-2 text-muted-foreground">{item.preview}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CalibreSection({ onAdd }: { onAdd: (b: Omit<CollageBlock, "id" | "addedAt">) => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CalibreItem[]>([]);
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  function handleQueryChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void doSearch(value), 400);
  }

  async function doSearch(q: string) {
    if (!q.trim()) { setResults([]); return; }
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setSearching(true);
    try {
      const res = await fetch(`${getBackendBaseURL()}/api/calibre/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
        body: JSON.stringify({ query: q.trim(), top_k: 5 }),
      });
      if (!res.ok) throw new Error(`Calibre ${res.status}`);
      const data = (await res.json()) as { items?: CalibreItem[] };
      setResults(Array.isArray(data.items) ? data.items : []);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="space-y-1.5">
      <SectionHeader label="Calibre" count={results.length || undefined} open={open} onToggle={() => setOpen((v) => !v)} />
      {open && (
        <div className="space-y-2 pl-1">
          <div className="relative">
            <Input
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              placeholder="Search Calibre library..."
              className="h-7 pr-7 text-xs"
            />
            <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
              {searching ? (
                <Loader2Icon className="size-3 animate-spin text-muted-foreground" />
              ) : (
                <SearchIcon className="size-3 text-muted-foreground" />
              )}
            </div>
          </div>
          {results.map((item, i) => (
            <div
              key={item.id ?? i}
              className="rounded-lg border border-l-2 border-l-amber-500/50 bg-card px-2.5 py-2 text-xs"
            >
              <div className="flex items-start justify-between gap-1">
                <div className="min-w-0">
                  <div className="font-medium leading-snug truncate">{item.title}</div>
                  {item.authors && (
                    <div className="text-muted-foreground">{item.authors}</div>
                  )}
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-5 shrink-0 px-1.5 text-[10px]"
                  onClick={() => {
                    const content = item.preview
                      ? `> **${item.title}**\n> ${item.preview}`
                      : `> **${item.title}**`;
                    onAdd({ source: "calibre", title: item.title, content });
                    toast.success("Added to canvas");
                  }}
                >
                  <PlusIcon className="size-2.5" />
                </Button>
              </div>
              {item.preview && (
                <p className="mt-0.5 line-clamp-2 text-muted-foreground">{item.preview}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ChatSection({ onAdd }: { onAdd: (b: Omit<CollageBlock, "id" | "addedAt">) => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ThreadResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleQueryChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void doSearch(value), 400);
  }

  async function doSearch(q: string) {
    if (!q.trim()) { setResults([]); return; }
    setSearching(true);
    try {
      const client = getAPIClient();
      const response = await client.threads.search({ limit: 5 });
      const all = response as ThreadResult[];
      const lower = q.toLowerCase();
      setResults(
        all.filter((t) => {
          const title = typeof t.metadata?.title === "string" ? t.metadata.title : "";
          return title.toLowerCase().includes(lower) || t.thread_id.includes(lower);
        }),
      );
      setUnavailable(false);
    } catch {
      setUnavailable(true);
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="space-y-1.5">
      <SectionHeader label="Chat" count={results.length || undefined} open={open} onToggle={() => setOpen((v) => !v)} />
      {open && (
        <div className="space-y-2 pl-1">
          {unavailable ? (
            <div className="text-muted-foreground rounded border border-dashed px-2 py-2 text-center text-xs">
              Chat unavailable
            </div>
          ) : (
            <>
              <div className="relative">
                <Input
                  value={query}
                  onChange={(e) => handleQueryChange(e.target.value)}
                  placeholder="Search chat threads..."
                  className="h-7 pr-7 text-xs"
                />
                <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
                  {searching ? (
                    <Loader2Icon className="size-3 animate-spin text-muted-foreground" />
                  ) : (
                    <SearchIcon className="size-3 text-muted-foreground" />
                  )}
                </div>
              </div>
              {results.map((thread) => {
                const meta = thread.metadata ?? {};
                const title =
                  typeof meta.title === "string" && meta.title
                    ? meta.title
                    : thread.thread_id.slice(0, 16);
                let snippet = "";
                const messages = thread.values?.messages;
                if (Array.isArray(messages)) {
                  const aiMsgs = messages.filter(
                    (m): m is Record<string, unknown> =>
                      typeof m === "object" && m !== null && (m as Record<string, unknown>).type === "ai",
                  );
                  const last = aiMsgs[aiMsgs.length - 1] as Record<string, unknown> | undefined;
                  if (typeof last?.content === "string") snippet = last.content.slice(0, 200);
                }
                return (
                  <div
                    key={thread.thread_id}
                    className="rounded-lg border border-l-2 border-l-violet-500/50 bg-card px-2.5 py-2 text-xs"
                  >
                    <div className="flex items-start justify-between gap-1">
                      <div className="min-w-0 font-medium leading-snug truncate">{title}</div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-5 shrink-0 px-1.5 text-[10px]"
                        onClick={() => {
                          onAdd({
                            source: "chat",
                            title,
                            content: snippet ? `**${title}**\n\n${snippet}` : `**${title}**`,
                          });
                          toast.success("Added to canvas");
                        }}
                      >
                        <PlusIcon className="size-2.5" />
                      </Button>
                    </div>
                    {snippet && (
                      <p className="mt-0.5 line-clamp-2 text-muted-foreground">{snippet}</p>
                    )}
                  </div>
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function PasteSection({ onAdd }: { onAdd: (b: Omit<CollageBlock, "id" | "addedAt">) => void }) {
  const [pasteTitle, setPasteTitle] = useState("");
  const [pasteContent, setPasteContent] = useState("");

  function handleAdd() {
    const content = pasteContent.trim();
    if (!content) { toast.error("Paste some content first"); return; }
    onAdd({
      source: "pasted",
      title: pasteTitle.trim() || "Pasted note",
      content,
    });
    setPasteTitle("");
    setPasteContent("");
    toast.success("Added to canvas");
  }

  return (
    <div className="space-y-1.5">
      <SectionHeader label="Paste" open={true} onToggle={() => undefined} />
      <div className="space-y-2 pl-1">
        <Input
          value={pasteTitle}
          onChange={(e) => setPasteTitle(e.target.value)}
          placeholder="Title (optional)"
          className="h-7 text-xs"
        />
        <Textarea
          value={pasteContent}
          onChange={(e) => setPasteContent(e.target.value)}
          placeholder="Paste anything — quotes, notes, excerpts..."
          className="min-h-[80px] text-xs"
        />
        <Button
          size="sm"
          className="w-full h-7 text-xs"
          onClick={handleAdd}
        >
          Add to canvas
        </Button>
      </div>
    </div>
  );
}

function MaterialBoard({ onAdd }: { onAdd: (b: Omit<CollageBlock, "id" | "addedAt">) => void }) {
  return (
    <div className="flex h-full flex-col rounded-l-3xl border-r border-border/70 bg-background/92 shadow-sm">
      <div className="shrink-0 border-b border-border/70 px-3 py-3">
        <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
          Material Drawer
        </div>
        <div className="mt-1 text-sm font-medium">Fragments and source pulls</div>
        <div className="mt-1 text-xs text-muted-foreground">
          Gather notes, quotes, excerpts, and search hits before arranging them.
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="space-y-3 p-3">
          <SurfSenseSection onAdd={onAdd} />
          <CalibreSection onAdd={onAdd} />
          <ChatSection onAdd={onAdd} />
          <PasteSection onAdd={onAdd} />
        </div>
      </ScrollArea>
    </div>
  );
}

// ─── Center: Assembly Canvas ──────────────────────────────────────────────────

function BlockCard({
  block,
  isSelected,
  isDragTarget,
  isDragging,
  onSelect,
  onRemove,
  onDragStart,
  onDragOver,
  onDrop,
}: {
  block: CollageBlock;
  isSelected: boolean;
  isDragTarget: boolean;
  isDragging: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onDragStart: (id: string) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      draggable
      onDragStart={() => onDragStart(block.id)}
      onDragOver={(e) => { e.preventDefault(); onDragOver(e); }}
      onDrop={(e) => { e.preventDefault(); onDrop(block.id); }}
      onClick={onSelect}
      className={cn(
        "cursor-pointer select-none rounded-2xl border border-l-2 border-border/70 bg-background/92 p-3 text-xs shadow-sm transition-all",
        SOURCE_BORDER[block.source],
        isDragging && "opacity-55",
        isSelected && "ring-2 ring-primary/50 bg-primary/5 shadow-md",
        isDragTarget && "ring-2 ring-primary/50 bg-primary/5 shadow-md",
      )}
    >
      <div className="flex items-start gap-2">
        <GripVerticalIcon className="mt-0.5 size-3.5 shrink-0 text-muted-foreground/50" />
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center justify-between gap-1">
            <SourceBadge source={block.source} />
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground"
                onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
                title={expanded ? "Collapse" : "Expand"}
              >
                {expanded ? (
                  <ChevronDownIcon className="size-3.5" />
                ) : (
                  <ChevronRightIcon className="size-3.5" />
                )}
              </button>
              <button
                type="button"
                className="text-muted-foreground hover:text-destructive"
                onClick={(e) => { e.stopPropagation(); onRemove(); }}
                title="Remove"
              >
                <XIcon className="size-3.5" />
              </button>
            </div>
          </div>
          <div className="truncate font-medium leading-snug">{block.title}</div>
          <p className={cn("text-muted-foreground", expanded ? "whitespace-pre-wrap" : "line-clamp-4")}>
            {block.content}
          </p>
        </div>
      </div>
    </div>
  );
}

function AssemblyCanvas({
  docTitle: initialTitle,
  blocks,
  selectedBlockId,
  synthesizing,
  onSelectBlock,
  onRemoveBlock,
  onReorder,
  onSynthesize,
}: {
  docTitle: string;
  blocks: CollageBlock[];
  selectedBlockId: string | null;
  synthesizing: boolean;
  onSelectBlock: (id: string) => void;
  onRemoveBlock: (id: string) => void;
  onReorder: (fromId: string, toId: string) => void;
  onSynthesize: () => void;
}) {
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  function handleDrop(targetId: string) {
    if (draggingId && draggingId !== targetId) {
      onReorder(draggingId, targetId);
    }
    setDraggingId(null);
    setDragOverId(null);
  }

  return (
    <div className="flex h-full flex-col border-r border-border/70 bg-[radial-gradient(circle_at_top,rgba(217,119,6,0.08),transparent_28%)]">
      <div className="shrink-0 border-b border-border/70 px-3 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0 flex items-center gap-2">
            <span className="truncate text-sm font-medium">{initialTitle}</span>
            {blocks.length > 0 && (
              <Badge variant="secondary" className="h-4 px-1 text-[10px] shrink-0">
                {blocks.length}
              </Badge>
            )}
          </div>
          <Button
            size="sm"
            className="h-8 shrink-0 gap-1 rounded-xl px-3 text-xs"
            disabled={blocks.length === 0 || synthesizing}
            onClick={onSynthesize}
          >
            {synthesizing ? (
              <Loader2Icon className="size-3 animate-spin" />
            ) : (
              <SparklesIcon className="size-3" />
            )}
            Stitch draft
          </Button>
        </div>
        <div className="mt-2 text-xs text-muted-foreground">
          Arrange blocks in rough sequence, then stitch them into a working draft.
        </div>
        {blocks.length > 1 ? (
          <div className="mt-2 text-[11px] text-muted-foreground">
            Drag fragments by the grip to reorder the collage.
          </div>
        ) : null}
      </div>
      <ScrollArea className="flex-1">
        <div className="space-y-2 p-3">
          {blocks.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/80 bg-background/60 px-4 py-8 text-center text-xs text-muted-foreground">
              Pull fragments from the drawer, paste loose notes, then stack them here in working order.
            </div>
          ) : (
            blocks.map((block) => (
              <BlockCard
                key={block.id}
                block={block}
                isSelected={selectedBlockId === block.id}
                isDragTarget={dragOverId === block.id}
                isDragging={draggingId === block.id}
                onSelect={() => onSelectBlock(block.id)}
                onRemove={() => onRemoveBlock(block.id)}
                onDragStart={(id) => setDraggingId(id)}
                onDragOver={() => setDragOverId(block.id)}
                onDrop={handleDrop}
              />
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

// ─── Right: Inspector ─────────────────────────────────────────────────────────

function Inspector({
  blocks,
  selectedBlockId,
  docId,
  docMarkdown,
  onRemoveBlock,
  onSwitchToEditor,
}: {
  blocks: CollageBlock[];
  selectedBlockId: string | null;
  docId: string;
  docMarkdown: string;
  onRemoveBlock: (id: string) => void;
  onSwitchToEditor: () => void;
}) {
  const updateDocument = useUpdateDocument(docId);
  const selectedBlock = blocks.find((b) => b.id === selectedBlockId) ?? null;

  const uniqueSources = Array.from(new Set(blocks.map((b) => b.source)));
  const totalWords = blocks.reduce((sum, b) => sum + b.content.trim().split(/\s+/).filter(Boolean).length, 0);

  async function handleInsertIntoEditor() {
    if (!selectedBlock) return;
    const newContent = docMarkdown
      ? `${docMarkdown}\n\n---\n\n${selectedBlock.content}`
      : selectedBlock.content;
    try {
      await updateDocument.mutateAsync({ content_markdown: newContent });
      onSwitchToEditor();
      toast.success("Dropped into Composer");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to insert");
    }
  }

  function handleExportMarkdown() {
    const md = blocks.map((b) => `## ${b.title}\n\n${b.content}`).join("\n\n---\n\n");
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = "collage-export.md";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex h-full flex-col rounded-r-3xl bg-background/92 shadow-sm">
      <div className="shrink-0 border-b border-border/70 px-3 py-3">
        <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
          Inspector
        </div>
        <div className="mt-1 text-sm font-medium">Selected fragment and desk stats</div>
      </div>
      <ScrollArea className="flex-1">
        <div className="space-y-4 p-3">
          {selectedBlock && (
            <div className="space-y-2">
              <div className="space-y-1">
                <SourceBadge source={selectedBlock.source} />
                <div className="text-xs text-muted-foreground">
                  Added {formatTimeAgo(selectedBlock.addedAt)}
                </div>
                <div className="text-xs text-muted-foreground">
                  {selectedBlock.content.trim().split(/\s+/).filter(Boolean).length} words
                </div>
              </div>
              <ScrollArea className="max-h-48 rounded-2xl border border-border/70 bg-muted/20">
                <pre className="whitespace-pre-wrap p-2 text-xs">{selectedBlock.content}</pre>
              </ScrollArea>
              <Button
                size="sm"
                variant="outline"
                className="w-full h-7 text-xs"
                disabled={updateDocument.isPending}
                onClick={() => void handleInsertIntoEditor()}
              >
                {updateDocument.isPending ? (
                  <Loader2Icon className="size-3 animate-spin" />
                ) : null}
                Append to Composer draft
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="w-full h-7 text-xs text-destructive hover:text-destructive"
                onClick={() => onRemoveBlock(selectedBlock.id)}
              >
                <XIcon className="size-3" />
                Remove from collage
              </Button>
              <div className="h-px bg-border" />
            </div>
          )}
          {!selectedBlock && (
            <div className="rounded-2xl border border-dashed border-border/80 bg-muted/20 px-4 py-6 text-sm text-muted-foreground">
              Select a fragment in the collage to inspect it, drop it into Composer, or remove it from the stack.
            </div>
          )}

          {/* Canvas stats */}
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Collage
            </div>
            <div className="space-y-1 text-xs text-muted-foreground">
              <div>{blocks.length} block{blocks.length !== 1 ? "s" : ""}</div>
              <div>{uniqueSources.length} source{uniqueSources.length !== 1 ? "s" : ""}</div>
              <div>~{totalWords} words</div>
            </div>
            {uniqueSources.length > 0 && (
              <div className="space-y-1">
                {uniqueSources.map((src) => {
                  const count = blocks.filter((b) => b.source === src).length;
                  return (
                    <div key={src} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span className={cn("size-2 rounded-full", SOURCE_DOT[src])} />
                      <span>{SOURCE_LABELS[src]}</span>
                      <span className="ml-auto">{count}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="h-px bg-border" />

          {/* Actions */}
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Actions
            </div>
            <Button
              size="sm"
              variant="outline"
              className="w-full h-7 text-xs"
              onClick={onSwitchToEditor}
            >
              Return to Composer draft
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="w-full h-7 text-xs"
              disabled={blocks.length === 0}
              onClick={handleExportMarkdown}
            >
              <DownloadIcon className="size-3" />
              Export collage as Markdown
            </Button>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}

// ─── Root: CollageWorkspace ───────────────────────────────────────────────────

export function CollageWorkspace({ document, onSwitchToEditor }: CollageWorkspaceProps) {
  const [blocks, setBlocks] = useState<CollageBlock[]>(() => loadBlocks(document.doc_id));
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [synthesizing, setSynthesizing] = useState(false);

  const updateDocument = useUpdateDocument(document.doc_id);
  const transformDocument = useTransformDocument(document.doc_id);

  // Persist whenever blocks change
  useEffect(() => {
    saveBlocks(document.doc_id, blocks);
  }, [blocks, document.doc_id]);

  function addBlock(partial: Omit<CollageBlock, "id" | "addedAt">) {
    const block: CollageBlock = {
      ...partial,
      id: crypto.randomUUID(),
      addedAt: Date.now(),
    };
    setBlocks((prev) => [...prev, block]);
    setSelectedBlockId(block.id);
  }

  function removeBlock(id: string) {
    setBlocks((prev) => prev.filter((b) => b.id !== id));
    if (selectedBlockId === id) setSelectedBlockId(null);
  }

  function reorderBlocks(fromId: string, toId: string) {
    setBlocks((prev) => {
      const arr = [...prev];
      const fromIdx = arr.findIndex((b) => b.id === fromId);
      const toIdx = arr.findIndex((b) => b.id === toId);
      if (fromIdx === -1 || toIdx === -1) return prev;
      const removed = arr.splice(fromIdx, 1);
      const item = removed[0];
      if (!item) return prev;
      arr.splice(toIdx, 0, item);
      return arr;
    });
  }

  async function handleSynthesize() {
    if (blocks.length === 0) return;
    setSynthesizing(true);
    const combined = blocks.map((b) => b.content).join("\n\n---\n\n");
    try {
      const result = await transformDocument.mutateAsync({
        document_markdown: combined,
        selection_markdown: combined,
        operation: "rewrite",
        instruction:
          "Synthesize these source blocks into a single coherent, well-structured document. Preserve the key ideas from each source. Remove redundancy.",
      });
      await updateDocument.mutateAsync({ content_markdown: result.transformed_markdown });
      toast.success(`Draft stitched with ${result.model_name}`);
      onSwitchToEditor();
    } catch {
      // Fallback: join blocks and switch
      try {
        await updateDocument.mutateAsync({ content_markdown: combined });
        toast.success("Fragments joined into a draft");
        onSwitchToEditor();
      } catch (err2) {
        toast.error(err2 instanceof Error ? err2.message : "Synthesize failed");
      }
    } finally {
      setSynthesizing(false);
    }
  }

  return (
    <div className="grid size-full min-h-0 gap-0 overflow-hidden rounded-3xl border border-border/70 bg-background/70 grid-cols-[280px_minmax(0,1fr)_280px] shadow-sm">
      <MaterialBoard onAdd={addBlock} />
      <AssemblyCanvas
        docTitle={document.title}
        blocks={blocks}
        selectedBlockId={selectedBlockId}
        synthesizing={synthesizing}
        onSelectBlock={setSelectedBlockId}
        onRemoveBlock={removeBlock}
        onReorder={reorderBlocks}
        onSynthesize={() => void handleSynthesize()}
      />
      <Inspector
        blocks={blocks}
        selectedBlockId={selectedBlockId}
        docId={document.doc_id}
        docMarkdown={document.content_markdown}
        onRemoveBlock={removeBlock}
        onSwitchToEditor={onSwitchToEditor}
      />
    </div>
  );
}
