"use client";

import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useDraggable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  BookmarkIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ClipboardCopyIcon,
  DownloadIcon,
  GripVerticalIcon,
  LayoutGridIcon,
  LayoutListIcon,
  Loader2Icon,
  NetworkIcon,
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
import { StructureCanvas } from "@/components/workspace/collage/structure-canvas";
import { getAPIClient } from "@/core/api";
import { getBackendBaseURL } from "@/core/config";
import type { BlockSource, CollageBlock } from "@/core/documents/collage-blocks";
import { loadBlocks, saveBlocks } from "@/core/documents/collage-blocks";
import { useTransformDocument, useUpdateDocument } from "@/core/documents/hooks";
import type { DocumentRecord } from "@/core/documents/types";
import { formatTimeAgo } from "@/core/utils/datetime";
import { cn } from "@/lib/utils";

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
  pinboard: "border-l-rose-500/60",
};

const SOURCE_BADGE: Record<BlockSource, string> = {
  surfsense: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  calibre: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  chat: "bg-violet-500/20 text-violet-400 border-violet-500/30",
  pasted: "bg-green-500/20 text-green-400 border-green-500/30",
  manual: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
  pinboard: "bg-rose-500/20 text-rose-400 border-rose-500/30",
};

const SOURCE_DOT: Record<BlockSource, string> = {
  surfsense: "bg-blue-400",
  calibre: "bg-amber-400",
  chat: "bg-violet-400",
  pasted: "bg-green-400",
  manual: "bg-zinc-400",
  pinboard: "bg-rose-400",
};

const SOURCE_LABELS: Record<BlockSource, string> = {
  surfsense: "SurfSense",
  calibre: "Calibre",
  chat: "Chat",
  pasted: "Pasted",
  manual: "Manual",
  pinboard: "Pinboard",
};

// ─── Shared helpers ───────────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-empty-function
function noop() {}

function wordCount(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  } catch {
    toast.error("Copy failed");
  }
}

// ─── Result card ──────────────────────────────────────────────────────────────

function ResultCard({
  source,
  title,
  preview,
  meta,
  onAdd,
  alreadyAdded,
}: {
  source: BlockSource;
  title: string;
  preview?: string;
  meta?: string;
  onAdd: () => void;
  alreadyAdded?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const borderClass = SOURCE_BORDER[source];
  const copyContent = preview ? `**${title}**\n\n${preview}` : `**${title}**`;
  const wc = preview ? wordCount(preview) : 0;

  return (
    <div
      className={cn(
        "rounded-lg border border-l-2 bg-card px-2.5 py-2 text-xs",
        borderClass,
        alreadyAdded && "opacity-60",
      )}
    >
      <div className="flex items-start justify-between gap-1">
        <div className="min-w-0 flex-1">
          <div className="font-medium leading-snug truncate">{title}</div>
          {meta && <div className="text-muted-foreground text-[10px] truncate">{meta}</div>}
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          {wc > 0 && (
            <span className="text-[10px] text-muted-foreground">{wc}w</span>
          )}
          <button
            type="button"
            title="Copy content"
            className="rounded p-0.5 text-muted-foreground hover:text-foreground"
            onClick={(e) => { e.stopPropagation(); void copyText(copyContent); }}
          >
            <ClipboardCopyIcon className="size-3" />
          </button>
          <Button
            size="sm"
            variant={alreadyAdded ? "secondary" : "ghost"}
            className="h-5 px-1.5 text-[10px]"
            onClick={onAdd}
            title={alreadyAdded ? "Already on canvas" : "Add to canvas"}
          >
            <PlusIcon className="size-2.5" />
          </Button>
        </div>
      </div>
      {preview && (
        <>
          <p className={cn("mt-1 text-muted-foreground", expanded ? "whitespace-pre-wrap" : "line-clamp-2")}>
            {preview}
          </p>
          <button
            type="button"
            className="mt-0.5 flex items-center gap-0.5 text-[10px] text-muted-foreground hover:text-foreground"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? (
              <><ChevronDownIcon className="size-3" /> Show less</>
            ) : (
              <><ChevronRightIcon className="size-3" /> Show full</>
            )}
          </button>
        </>
      )}
    </div>
  );
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

type CalibreItem = { id?: number; title: string; authors?: string; year?: string | number; preview?: string };

// ─── Pinboard helpers ─────────────────────────────────────────────────────────

type PinboardItem = { url: string; title: string; description?: string; tags?: string[]; created_at?: string };

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
      className="sticky top-0 z-10 flex w-full items-center gap-1.5 bg-background/90 py-1 text-left backdrop-blur-sm"
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

// ─── Left: Material Board sections ───────────────────────────────────────────

function useSearchSection<T>({
  fetch: doFetch,
}: {
  fetch: (q: string, ctrl: AbortController) => Promise<T[]>;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<T[]>([]);
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  function handleQueryChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void run(value), 400);
  }

  async function run(q: string) {
    if (!q.trim()) { setResults([]); return; }
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setSearching(true);
    try {
      const items = await doFetch(q, ctrl);
      if (!ctrl.signal.aborted) setResults(items);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      if (!ctrl.signal.aborted) setResults([]);
    } finally {
      if (!ctrl.signal.aborted) setSearching(false);
    }
  }

  return { query, results, searching, handleQueryChange };
}

function SearchInput({
  value,
  onChange,
  placeholder,
  searching,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  searching: boolean;
}) {
  return (
    <div className="relative">
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
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
  );
}

function SurfSenseSection({
  onAdd,
  addedTitles,
}: {
  onAdd: (b: Omit<CollageBlock, "id" | "addedAt">) => void;
  addedTitles: Set<string>;
}) {
  const [open, setOpen] = useState(true);
  const { query, results, searching, handleQueryChange } = useSearchSection<SSResult>({
    fetch: async (q, ctrl) => {
      const res = await fetch(`${getBackendBaseURL()}/api/surfsense/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
        body: JSON.stringify({ query: q.trim(), top_k: 8 }),
      });
      if (!res.ok) throw new Error(`SurfSense ${res.status}`);
      return normalizeSSResults(await res.json());
    },
  });

  return (
    <div className="space-y-1.5">
      <SectionHeader label="SurfSense" count={results.length || undefined} open={open} onToggle={() => setOpen((v) => !v)} />
      {open && (
        <div className="space-y-2 pl-1">
          <SearchInput value={query} onChange={handleQueryChange} placeholder="Search SurfSense..." searching={searching} />
          {results.length === 0 && query.trim() && !searching && (
            <p className="text-center text-[10px] text-muted-foreground">No results for &ldquo;{query}&rdquo;</p>
          )}
          {results.map((item, i) => (
            <ResultCard
              key={item.id ?? i}
              source="surfsense"
              title={item.title}
              preview={item.preview}
              alreadyAdded={addedTitles.has(item.title)}
              onAdd={() => {
                onAdd({
                  source: "surfsense",
                  title: item.title,
                  content: item.preview ? `> **${item.title}**\n> ${item.preview}` : `> **${item.title}**`,
                });
                toast.success("Added to canvas");
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CalibreSection({
  onAdd,
  addedTitles,
}: {
  onAdd: (b: Omit<CollageBlock, "id" | "addedAt">) => void;
  addedTitles: Set<string>;
}) {
  const [open, setOpen] = useState(false);
  const { query, results, searching, handleQueryChange } = useSearchSection<CalibreItem>({
    fetch: async (q, ctrl) => {
      const res = await fetch(`${getBackendBaseURL()}/api/calibre/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
        body: JSON.stringify({ query: q.trim(), top_k: 8 }),
      });
      if (!res.ok) throw new Error(`Calibre ${res.status}`);
      const data = (await res.json()) as { items?: CalibreItem[] };
      return Array.isArray(data.items) ? data.items : [];
    },
  });

  return (
    <div className="space-y-1.5">
      <SectionHeader label="Calibre" count={results.length || undefined} open={open} onToggle={() => setOpen((v) => !v)} />
      {open && (
        <div className="space-y-2 pl-1">
          <SearchInput value={query} onChange={handleQueryChange} placeholder="Search Calibre library..." searching={searching} />
          {results.length === 0 && query.trim() && !searching && (
            <p className="text-center text-[10px] text-muted-foreground">No results for &ldquo;{query}&rdquo;</p>
          )}
          {results.map((item, i) => (
            <ResultCard
              key={item.id ?? i}
              source="calibre"
              title={item.title}
              preview={item.preview}
              meta={[item.authors, item.year ? String(item.year) : undefined].filter(Boolean).join(" · ")}
              alreadyAdded={addedTitles.has(item.title)}
              onAdd={() => {
                const content = item.preview
                  ? `> **${item.title}**\n> ${item.preview}`
                  : `> **${item.title}**`;
                onAdd({ source: "calibre", title: item.title, content });
                toast.success("Added to canvas");
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PinboardSection({
  onAdd,
  addedTitles,
}: {
  onAdd: (b: Omit<CollageBlock, "id" | "addedAt">) => void;
  addedTitles: Set<string>;
}) {
  const [open, setOpen] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const { query, results, searching, handleQueryChange } = useSearchSection<PinboardItem>({
    fetch: async (q, ctrl) => {
      const res = await fetch(`${getBackendBaseURL()}/api/pinboard/bookmarks/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
        body: JSON.stringify({ query: q.trim(), top_k: 8 }),
      });
      if (res.status === 503 || res.status === 404) {
        setUnavailable(true);
        return [];
      }
      if (!res.ok) throw new Error(`Pinboard ${res.status}`);
      setUnavailable(false);
      const data = (await res.json()) as { bookmarks?: PinboardItem[]; results?: PinboardItem[] } | PinboardItem[];
      if (Array.isArray(data)) return data;
      return (data as { bookmarks?: PinboardItem[]; results?: PinboardItem[] }).bookmarks ??
        (data as { results?: PinboardItem[] }).results ?? [];
    },
  });

  return (
    <div className="space-y-1.5">
      <SectionHeader label="Pinboard" count={results.length || undefined} open={open} onToggle={() => setOpen((v) => !v)} />
      {open && (
        <div className="space-y-2 pl-1">
          {unavailable ? (
            <div className="text-muted-foreground flex items-center gap-1.5 rounded border border-dashed px-2 py-2 text-[10px]">
              <BookmarkIcon className="size-3 shrink-0" />
              Pinboard not configured — add your API token in settings.
            </div>
          ) : (
            <>
              <SearchInput value={query} onChange={handleQueryChange} placeholder="Search bookmarks..." searching={searching} />
              {results.length === 0 && query.trim() && !searching && (
                <p className="text-center text-[10px] text-muted-foreground">No results for &ldquo;{query}&rdquo;</p>
              )}
              {results.map((item, i) => {
                const content = item.description
                  ? `> **${item.title}**\n> ${item.url}\n>\n> ${item.description}`
                  : `> **${item.title}**\n> ${item.url}`;
                return (
                  <ResultCard
                    key={i}
                    source="pinboard"
                    title={item.title}
                    preview={item.description ?? item.url}
                    meta={item.tags?.join(", ")}
                    alreadyAdded={addedTitles.has(item.title)}
                    onAdd={() => {
                      onAdd({ source: "pinboard", title: item.title, content });
                      toast.success("Added to canvas");
                    }}
                  />
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ChatSection({
  onAdd,
  addedTitles,
}: {
  onAdd: (b: Omit<CollageBlock, "id" | "addedAt">) => void;
  addedTitles: Set<string>;
}) {
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
              <SearchInput value={query} onChange={handleQueryChange} placeholder="Search chat threads..." searching={searching} />
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
                  if (typeof last?.content === "string") snippet = last.content.slice(0, 300);
                }
                return (
                  <ResultCard
                    key={thread.thread_id}
                    source="chat"
                    title={title}
                    preview={snippet || undefined}
                    alreadyAdded={addedTitles.has(title)}
                    onAdd={() => {
                      onAdd({
                        source: "chat",
                        title,
                        content: snippet ? `**${title}**\n\n${snippet}` : `**${title}**`,
                      });
                      toast.success("Added to canvas");
                    }}
                  />
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

function MaterialBoard({
  onAdd,
  addedBlocks,
}: {
  onAdd: (b: Omit<CollageBlock, "id" | "addedAt">) => void;
  addedBlocks: CollageBlock[];
}) {
  const addedTitles = new Set(addedBlocks.map((b) => b.title));

  return (
    <div className="flex h-full flex-col rounded-l-3xl border-r border-border/70 bg-background/92 shadow-sm">
      <div className="shrink-0 border-b border-border/70 px-3 py-3">
        <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
          Materials
        </div>
        <div className="mt-0.5 text-sm font-medium">Fragments and source pulls</div>
        <div className="mt-0.5 text-[10px] text-muted-foreground">
          Search, copy, or add any result to the canvas.
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="space-y-3 p-3">
          <SurfSenseSection onAdd={onAdd} addedTitles={addedTitles} />
          <CalibreSection onAdd={onAdd} addedTitles={addedTitles} />
          <PinboardSection onAdd={onAdd} addedTitles={addedTitles} />
          <ChatSection onAdd={onAdd} addedTitles={addedTitles} />
          <PasteSection onAdd={onAdd} />
        </div>
      </ScrollArea>
    </div>
  );
}

// ─── Center: Board Canvas (spatial free-form view) ────────────────────────────

function BoardCanvas({
  blocks,
  selectedBlockId,
  onSelectBlock,
  onRemoveBlock,
  onUpdatePosition,
}: {
  blocks: CollageBlock[];
  selectedBlockId: string | null;
  onSelectBlock: (id: string) => void;
  onRemoveBlock: (id: string) => void;
  onUpdatePosition: (id: string, x: number, y: number) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, delta } = event;
    const block = blocks.find((b) => b.id === active.id);
    if (!block) return;
    const newX = (block.x ?? 0) + delta.x;
    const newY = (block.y ?? 0) + delta.y;
    onUpdatePosition(active.id as string, newX, newY);
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div className="relative flex-1 overflow-auto">
        <div className="relative" style={{ minWidth: 900, minHeight: 700 }}>
          {blocks.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="rounded-2xl border border-dashed border-border/80 bg-background/60 px-8 py-10 text-center text-xs text-muted-foreground">
                Pull fragments from the Materials drawer, then arrange them freely on the canvas.
              </div>
            </div>
          )}
          {blocks.map((block, idx) => (
            <BoardCard
              key={block.id}
              block={block}
              idx={idx}
              isSelected={selectedBlockId === block.id}
              onSelect={() => onSelectBlock(block.id)}
              onRemove={() => onRemoveBlock(block.id)}
            />
          ))}
        </div>
      </div>
    </DndContext>
  );
}

function BoardCard({
  block,
  idx,
  isSelected,
  onSelect,
  onRemove,
}: {
  block: CollageBlock;
  idx: number;
  isSelected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: block.id });

  const x = block.x ?? 24 + (idx % 3) * 210;
  const y = block.y ?? 24 + Math.floor(idx / 3) * 180;

  const style: React.CSSProperties = {
    position: "absolute",
    left: x + (transform?.x ?? 0),
    top: y + (transform?.y ?? 0),
    width: 200,
    zIndex: isDragging ? 50 : 1,
    opacity: isDragging ? 0.85 : 1,
    cursor: isDragging ? "grabbing" : "default",
  };

  return (
    <div ref={setNodeRef} style={style}>
      <div
        onClick={onSelect}
        className={cn(
          "select-none rounded-2xl border border-l-2 border-border/70 bg-background/95 p-3 text-xs shadow-sm transition-shadow",
          SOURCE_BORDER[block.source],
          isSelected && "ring-2 ring-primary/50 shadow-md",
          isDragging && "shadow-xl",
        )}
      >
        <div className="flex items-start gap-1.5">
          <GripVerticalIcon
            {...listeners}
            {...attributes}
            className="mt-0.5 size-3.5 shrink-0 cursor-grab text-muted-foreground/50 active:cursor-grabbing"
          />
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex items-center justify-between gap-1">
              <SourceBadge source={block.source} />
              <button
                type="button"
                className="text-muted-foreground hover:text-destructive"
                onClick={(e) => { e.stopPropagation(); onRemove(); }}
              >
                <XIcon className="size-3" />
              </button>
            </div>
            <div className="truncate font-medium leading-snug">{block.title}</div>
            <p className="line-clamp-3 text-muted-foreground">{block.content}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Center: Assembly Canvas ──────────────────────────────────────────────────

function BlockCard({
  block,
  isSelected,
  onSelect,
  onRemove,
  overlay = false,
}: {
  block: CollageBlock;
  isSelected: boolean;
  onSelect: () => void;
  onRemove: () => void;
  overlay?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const wc = wordCount(block.content);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={overlay ? undefined : setNodeRef}
      style={overlay ? undefined : style}
      onClick={onSelect}
      className={cn(
        "cursor-pointer select-none rounded-2xl border border-l-2 border-border/70 bg-background/92 p-3 text-xs shadow-sm transition-colors",
        SOURCE_BORDER[block.source],
        isDragging && !overlay && "opacity-30",
        overlay && "rotate-1 shadow-lg opacity-90",
        isSelected && !isDragging && "ring-2 ring-primary/50 bg-primary/5 shadow-md",
      )}
    >
      <div className="flex items-start gap-2">
        <GripVerticalIcon
          {...(overlay ? {} : { ...listeners, ...attributes })}
          className="mt-0.5 size-3.5 shrink-0 cursor-grab text-muted-foreground/50 active:cursor-grabbing"
        />
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center justify-between gap-1">
            <SourceBadge source={block.source} />
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-muted-foreground">{wc}w</span>
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground"
                onClick={(e) => { e.stopPropagation(); void copyText(block.content); }}
                title="Copy content"
              >
                <ClipboardCopyIcon className="size-3.5" />
              </button>
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
  canvasView,
  onSelectBlock,
  onRemoveBlock,
  onReorder,
  onUpdateBlockPosition,
  onSynthesize,
  onCanvasViewChange,
}: {
  docTitle: string;
  blocks: CollageBlock[];
  selectedBlockId: string | null;
  synthesizing: boolean;
  canvasView: "list" | "board" | "structure";
  onSelectBlock: (id: string) => void;
  onRemoveBlock: (id: string) => void;
  onReorder: (fromId: string, toId: string) => void;
  onUpdateBlockPosition: (id: string, x: number, y: number) => void;
  onSynthesize: (orderedIds?: string[]) => void;
  onCanvasViewChange: (view: "list" | "board" | "structure") => void;
}) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const activeBlock = blocks.find((b) => b.id === activeId) ?? null;

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const { active, over } = event;
    if (over && active.id !== over.id) {
      onReorder(active.id as string, over.id as string);
    }
  }

  const blockIds = blocks.map((b) => b.id);

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
          <div className="flex items-center gap-1.5">
            {/* Canvas view toggle */}
            <div className="flex items-center gap-0.5 rounded-lg border border-border/60 bg-muted/30 p-0.5">
              <button
                type="button"
                title="List view"
                onClick={() => onCanvasViewChange("list")}
                className={cn(
                  "flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground",
                  canvasView === "list" && "bg-background text-foreground shadow-sm",
                )}
              >
                <LayoutListIcon className="size-3" />
              </button>
              <button
                type="button"
                title="Board view"
                onClick={() => onCanvasViewChange("board")}
                className={cn(
                  "flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground",
                  canvasView === "board" && "bg-background text-foreground shadow-sm",
                )}
              >
                <LayoutGridIcon className="size-3" />
              </button>
              <button
                type="button"
                title="Structure view"
                onClick={() => onCanvasViewChange("structure")}
                className={cn(
                  "flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground",
                  canvasView === "structure" && "bg-background text-foreground shadow-sm",
                )}
              >
                <NetworkIcon className="size-3" />
              </button>
            </div>
            <Button
              size="sm"
              className="h-8 shrink-0 gap-1 rounded-xl px-3 text-xs"
              disabled={blocks.length === 0 || synthesizing}
              onClick={() => onSynthesize()}
            >
              {synthesizing ? (
                <Loader2Icon className="size-3 animate-spin" />
              ) : (
                <SparklesIcon className="size-3" />
              )}
              Stitch draft
            </Button>
          </div>
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          {canvasView === "list" && "Drag by grip to reorder, then stitch into a working draft."}
          {canvasView === "board" && "Drag blocks freely to arrange spatially, then stitch."}
          {canvasView === "structure" && "Draw edges to define narrative flow, then stitch in order."}
        </div>
      </div>

      {canvasView === "list" && (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={(e) => setActiveId(e.active.id as string)}
          onDragEnd={handleDragEnd}
          onDragCancel={() => setActiveId(null)}
        >
          <SortableContext items={blockIds} strategy={verticalListSortingStrategy}>
            <ScrollArea className="flex-1">
              <div className="space-y-2 p-3">
                {blocks.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-border/80 bg-background/60 px-4 py-8 text-center text-xs text-muted-foreground">
                    Pull fragments from the Materials drawer, paste notes, then stack them here in working order.
                  </div>
                ) : (
                  blocks.map((block) => (
                    <BlockCard
                      key={block.id}
                      block={block}
                      isSelected={selectedBlockId === block.id}
                      onSelect={() => onSelectBlock(block.id)}
                      onRemove={() => onRemoveBlock(block.id)}
                    />
                  ))
                )}
              </div>
            </ScrollArea>
          </SortableContext>
          <DragOverlay dropAnimation={{ duration: 150, easing: "ease" }}>
            {activeBlock && (
              <BlockCard
                block={activeBlock}
                isSelected={false}
                onSelect={noop}
                onRemove={noop}
                overlay
              />
            )}
          </DragOverlay>
        </DndContext>
      )}

      {canvasView === "board" && (
        <BoardCanvas
          blocks={blocks}
          selectedBlockId={selectedBlockId}
          onSelectBlock={onSelectBlock}
          onRemoveBlock={onRemoveBlock}
          onUpdatePosition={onUpdateBlockPosition}
        />
      )}

      {canvasView === "structure" && (
        <div className="flex flex-1 flex-col overflow-hidden">
          <StructureCanvas
            blocks={blocks}
            synthesizing={synthesizing}
            onSynthesize={onSynthesize}
          />
        </div>
      )}
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
  const totalWords = blocks.reduce((sum, b) => sum + wordCount(b.content), 0);

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
        <div className="mt-0.5 text-sm font-medium">Fragment detail</div>
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
                  {wordCount(selectedBlock.content)} words
                </div>
              </div>
              <ScrollArea className="max-h-48 rounded-2xl border border-border/70 bg-muted/20">
                <pre className="whitespace-pre-wrap p-2 text-xs">{selectedBlock.content}</pre>
              </ScrollArea>
              <Button
                size="sm"
                variant="outline"
                className="w-full h-7 text-xs"
                onClick={() => void copyText(selectedBlock.content)}
              >
                <ClipboardCopyIcon className="size-3" />
                Copy content
              </Button>
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
              Select a fragment to inspect it, copy it, drop it into Composer, or remove it.
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
              Return to Composer
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="w-full h-7 text-xs"
              disabled={blocks.length === 0}
              onClick={handleExportMarkdown}
            >
              <DownloadIcon className="size-3" />
              Export as Markdown
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
  const [canvasView, setCanvasView] = useState<"list" | "board" | "structure">("list");

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
      const fromIdx = prev.findIndex((b) => b.id === fromId);
      const toIdx = prev.findIndex((b) => b.id === toId);
      if (fromIdx === -1 || toIdx === -1) return prev;
      return arrayMove(prev, fromIdx, toIdx);
    });
  }

  function updateBlockPosition(id: string, x: number, y: number) {
    setBlocks((prev) => prev.map((b) => (b.id === id ? { ...b, x, y } : b)));
  }

  async function handleSynthesize(orderedIds?: string[]) {
    if (blocks.length === 0) return;
    setSynthesizing(true);
    const ordered = orderedIds
      ? orderedIds.map((id) => blocks.find((b) => b.id === id)).filter(Boolean) as CollageBlock[]
      : blocks;
    const combined = ordered.map((b) => b.content).join("\n\n---\n\n");
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
      <MaterialBoard onAdd={addBlock} addedBlocks={blocks} />
      <AssemblyCanvas
        docTitle={document.title}
        blocks={blocks}
        selectedBlockId={selectedBlockId}
        synthesizing={synthesizing}
        canvasView={canvasView}
        onSelectBlock={setSelectedBlockId}
        onRemoveBlock={removeBlock}
        onReorder={reorderBlocks}
        onUpdateBlockPosition={updateBlockPosition}
        onSynthesize={(ids) => void handleSynthesize(ids)}
        onCanvasViewChange={setCanvasView}
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
