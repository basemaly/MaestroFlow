"use client";

import {
  ChevronDownIcon,
  ChevronRightIcon,
  Loader2Icon,
  PlusIcon,
  SearchIcon,
  XIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { getAPIClient } from "@/core/api";
import { apiFetch, readApiError } from "@/core/api/fetch";
import { getBackendBaseURL } from "@/core/config";
import { searchPinboardBookmarks } from "@/core/pinboard/api";
import type { PinboardBookmark } from "@/core/pinboard/types";

// ─── Types ────────────────────────────────────────────────────────────────────

type ClipSource = "surfsense" | "calibre" | "chat" | "pasted" | "pinboard";

interface Clip {
  id: string;
  source: ClipSource;
  title: string;
  content: string;
  addedAt: number;
}

interface ClipsBoardProps {
  docId: string;
  onInsert: (text: string) => void;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const SOURCE_COLORS: Record<ClipSource, string> = {
  surfsense: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  calibre: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  chat: "bg-violet-500/20 text-violet-400 border-violet-500/30",
  pasted: "bg-green-500/20 text-green-400 border-green-500/30",
  pinboard: "bg-rose-500/20 text-rose-400 border-rose-500/30",
};

const SOURCE_LABELS: Record<ClipSource, string> = {
  surfsense: "SurfSense",
  calibre: "Calibre",
  chat: "Chat",
  pasted: "Pasted",
  pinboard: "Pinboard",
};

// ─── Persistence helpers ───────────────────────────────────────────────────────

function loadClips(docId: string): Clip[] {
  try {
    const raw = localStorage.getItem(`maestroflow:clips:${docId}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed as Clip[];
  } catch {
    return [];
  }
}

function saveClips(docId: string, clips: Clip[]) {
  try {
    localStorage.setItem(`maestroflow:clips:${docId}`, JSON.stringify(clips));
  } catch {
    // ignore quota errors
  }
}

// ─── Normalize SurfSense response ─────────────────────────────────────────────

type SurfSenseResult = { id?: number; title: string; preview?: string };

function normalizeSSResults(payload: unknown): SurfSenseResult[] {
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

// ─── Calibre result type ──────────────────────────────────────────────────────

type CalibreItem = { id?: number; title: string; authors?: string; preview?: string };

type PinboardItem = PinboardBookmark;

// ─── Source badge ─────────────────────────────────────────────────────────────

function SourceBadge({ source }: { source: ClipSource }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium ${SOURCE_COLORS[source]}`}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {SOURCE_LABELS[source]}
    </span>
  );
}

// ─── Stash clip card ──────────────────────────────────────────────────────────

function StashClipCard({
  clip,
  onInsert,
  onRemove,
}: {
  clip: Clip;
  onInsert: (text: string) => void;
  onRemove: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-1">
          <SourceBadge source={clip.source} />
          <span className="truncate font-medium leading-snug">{clip.title}</span>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground"
            onClick={() => setExpanded((v) => !v)}
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
            onClick={() => onRemove(clip.id)}
            title="Remove"
          >
            <XIcon className="size-3.5" />
          </button>
        </div>
      </div>
      <p className={`mt-1 text-muted-foreground ${expanded ? "whitespace-pre-wrap" : "line-clamp-3"}`}>
        {clip.content}
      </p>
      <Button
        size="sm"
        variant="ghost"
        className="mt-1 h-6 px-2 text-xs"
        onClick={() => {
          onInsert(clip.content);
          toast.success("Inserted at cursor");
        }}
      >
        ↓ Insert
      </Button>
    </div>
  );
}

// ─── Stash section ────────────────────────────────────────────────────────────

function StashSection({
  clips,
  onInsert,
  onRemove,
}: {
  clips: Clip[];
  onInsert: (text: string) => void;
  onRemove: (id: string) => void;
}) {
  if (clips.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="h-px flex-1 bg-border" />
        <span className="text-muted-foreground text-[10px] font-medium uppercase tracking-wider">
          In your stash
        </span>
        <div className="h-px flex-1 bg-border" />
      </div>
      <ScrollArea className="max-h-[50vh]">
        <div className="space-y-2 pr-1">
          {clips.map((clip) => (
            <StashClipCard
              key={clip.id}
              clip={clip}
              onInsert={onInsert}
              onRemove={onRemove}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

// ─── SurfSense tab ────────────────────────────────────────────────────────────

function SurfSenseTab({
  stash,
  onAddToStash,
}: {
  stash: Clip[];
  onAddToStash: (clip: Omit<Clip, "id" | "addedAt">) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SurfSenseResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  function handleQueryChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void doSearch(value);
    }, 400);
  }

  async function doSearch(q: string) {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsSearching(true);
    try {
      const response = await apiFetch(`${getBackendBaseURL()}/api/surfsense/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({ query: q.trim(), top_k: 6 }),
      });
      if (!response.ok) throw await readApiError(response, "SurfSense search failed");
      const data: unknown = await response.json();
      setResults(normalizeSSResults(data));
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      toast.error(err instanceof Error ? err.message : "SurfSense search failed");
    } finally {
      setIsSearching(false);
    }
  }

  const stashedIds = new Set(stash.filter((c) => c.source === "surfsense").map((c) => c.title));

  return (
    <div className="space-y-3">
      <div className="relative">
        <Input
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          placeholder="Search SurfSense..."
          className="h-8 pr-8 text-sm"
        />
        <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
          {isSearching ? (
            <Loader2Icon className="size-3.5 animate-spin text-muted-foreground" />
          ) : (
            <SearchIcon className="size-3.5 text-muted-foreground" />
          )}
        </div>
      </div>

      {results.length > 0 && (
        <div className="space-y-2">
          {results.map((item, i) => {
            const alreadyStashed = stashedIds.has(item.title);
            return (
              <div key={item.id ?? i} className="rounded-lg border bg-muted/30 px-3 py-2 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <SourceBadge source="surfsense" />
                    <div className="mt-1 font-medium leading-snug">{item.title}</div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="mt-0.5 h-6 shrink-0 px-2 text-xs"
                    disabled={alreadyStashed}
                    onClick={() => {
                      const content = item.preview
                        ? `> **${item.title}**\n> ${item.preview}`
                        : `> **${item.title}**`;
                      onAddToStash({ source: "surfsense", title: item.title, content });
                    }}
                  >
                    <PlusIcon className="size-3" />
                    {alreadyStashed ? "Added" : "Add"}
                  </Button>
                </div>
                {item.preview && (
                  <p className="mt-1 line-clamp-2 text-muted-foreground">{item.preview}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Calibre tab ──────────────────────────────────────────────────────────────

function CalibreTab({
  stash,
  onAddToStash,
}: {
  stash: Clip[];
  onAddToStash: (clip: Omit<Clip, "id" | "addedAt">) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CalibreItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  function handleQueryChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void doSearch(value);
    }, 400);
  }

  async function doSearch(q: string) {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsSearching(true);
    try {
      const response = await apiFetch(`${getBackendBaseURL()}/api/calibre/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({ query: q.trim(), top_k: 6 }),
      });
      if (!response.ok) throw await readApiError(response, "Calibre search failed");
      const data = (await response.json()) as { items?: CalibreItem[] };
      setResults(Array.isArray(data.items) ? data.items : []);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      toast.error(err instanceof Error ? err.message : "Calibre search failed");
    } finally {
      setIsSearching(false);
    }
  }

  const stashedTitles = new Set(stash.filter((c) => c.source === "calibre").map((c) => c.title));

  return (
    <div className="space-y-3">
      <div className="relative">
        <Input
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          placeholder="Search Calibre library..."
          className="h-8 pr-8 text-sm"
        />
        <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
          {isSearching ? (
            <Loader2Icon className="size-3.5 animate-spin text-muted-foreground" />
          ) : (
            <SearchIcon className="size-3.5 text-muted-foreground" />
          )}
        </div>
      </div>

      {results.length > 0 && (
        <div className="space-y-2">
          {results.map((item, i) => {
            const alreadyStashed = stashedTitles.has(item.title);
            return (
              <div key={item.id ?? i} className="rounded-lg border bg-muted/30 px-3 py-2 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <SourceBadge source="calibre" />
                    <div className="mt-1 font-medium leading-snug">{item.title}</div>
                    {item.authors && (
                      <div className="text-muted-foreground">{item.authors}</div>
                    )}
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="mt-0.5 h-6 shrink-0 px-2 text-xs"
                    disabled={alreadyStashed}
                    onClick={() => {
                      const content = item.preview
                        ? `> **${item.title}**\n> ${item.preview}`
                        : `> **${item.title}**`;
                      onAddToStash({ source: "calibre", title: item.title, content });
                    }}
                  >
                    <PlusIcon className="size-3" />
                    {alreadyStashed ? "Added" : "Add"}
                  </Button>
                </div>
                {item.preview && (
                  <p className="mt-1 line-clamp-2 text-muted-foreground">{item.preview}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Chat tab ─────────────────────────────────────────────────────────────────

type ThreadResult = {
  thread_id: string;
  metadata: Record<string, unknown>;
  values?: Record<string, unknown>;
};

function ChatTab({
  stash,
  onAddToStash,
}: {
  stash: Clip[];
  onAddToStash: (clip: Omit<Clip, "id" | "addedAt">) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ThreadResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleQueryChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void doSearch(value);
    }, 400);
  }

  async function doSearch(q: string) {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    setIsSearching(true);
    try {
      const apiClient = getAPIClient();
      const response = await apiClient.threads.search({ limit: 5 });
      const all = response as ThreadResult[];
      const lower = q.toLowerCase();
      const filtered = all.filter((t) => {
        const meta = t.metadata ?? {};
        const title = typeof meta.title === "string" ? meta.title : "";
        return title.toLowerCase().includes(lower) || t.thread_id.includes(lower);
      });
      setResults(filtered);
      setUnavailable(false);
    } catch {
      setUnavailable(true);
    } finally {
      setIsSearching(false);
    }
  }

  const stashedIds = new Set(stash.filter((c) => c.source === "chat").map((c) => c.title));

  if (unavailable) {
    return (
      <div className="text-muted-foreground rounded-lg border border-dashed px-3 py-4 text-center text-xs">
        Chat search unavailable
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <Input
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          placeholder="Search chat threads..."
          className="h-8 pr-8 text-sm"
        />
        <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
          {isSearching ? (
            <Loader2Icon className="size-3.5 animate-spin text-muted-foreground" />
          ) : (
            <SearchIcon className="size-3.5 text-muted-foreground" />
          )}
        </div>
      </div>

      {results.length > 0 && (
        <div className="space-y-2">
          {results.map((thread) => {
            const meta = thread.metadata ?? {};
            const title =
              typeof meta.title === "string" && meta.title
                ? meta.title
                : thread.thread_id.slice(0, 16);

            // Try to extract last AI message snippet from values
            let snippet = "";
            const values = thread.values ?? {};
            const messages = values.messages;
            if (Array.isArray(messages)) {
              const aiMsgs = messages.filter(
                (m): m is Record<string, unknown> =>
                  typeof m === "object" && m !== null && (m as Record<string, unknown>).type === "ai",
              );
              if (aiMsgs.length > 0) {
                const last = aiMsgs[aiMsgs.length - 1] as Record<string, unknown> | undefined;
                const content = last?.content;
                if (typeof content === "string") {
                  snippet = content.slice(0, 200);
                }
              }
            }

            const alreadyStashed = stashedIds.has(title);

            return (
              <div
                key={thread.thread_id}
                className="rounded-lg border bg-muted/30 px-3 py-2 text-xs"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <SourceBadge source="chat" />
                    <div className="mt-1 font-medium leading-snug">{title}</div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="mt-0.5 h-6 shrink-0 px-2 text-xs"
                    disabled={alreadyStashed}
                    onClick={() => {
                      const content = snippet
                        ? `**${title}**\n\n${snippet}`
                        : `**${title}**`;
                      onAddToStash({ source: "chat", title, content });
                    }}
                  >
                    <PlusIcon className="size-3" />
                    {alreadyStashed ? "Added" : "Add"}
                  </Button>
                </div>
                {snippet && (
                  <p className="mt-1 line-clamp-2 text-muted-foreground">{snippet}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Paste tab ────────────────────────────────────────────────────────────────

function PasteTab({
  onAddToStash,
}: {
  onAddToStash: (clip: Omit<Clip, "id" | "addedAt">) => void;
}) {
  const [pasteTitle, setPasteTitle] = useState("");
  const [pasteContent, setPasteContent] = useState("");

  function handleAdd() {
    const content = pasteContent.trim();
    if (!content) {
      toast.error("Paste some content first");
      return;
    }
    onAddToStash({
      source: "pasted",
      title: pasteTitle.trim() || "Pasted note",
      content,
    });
    setPasteContent("");
    setPasteTitle("");
    toast.success("Added to stash");
  }

  return (
    <div className="space-y-2">
      <Input
        value={pasteTitle}
        onChange={(e) => setPasteTitle(e.target.value)}
        placeholder="Title (optional)"
        className="h-8 text-sm"
      />
      <Textarea
        value={pasteContent}
        onChange={(e) => setPasteContent(e.target.value)}
        placeholder="Paste text, quotes, or notes here..."
        className="min-h-28 text-sm"
      />
      <Button size="sm" className="w-full" onClick={handleAdd}>
        <PlusIcon className="size-3.5" />
        Add to stash
      </Button>
    </div>
  );
}

function formatPinboardClip(item: PinboardItem) {
  const lines = [`**${item.title}**`, item.url];
  if (item.tags.length) {
    lines.push(`Tags: ${item.tags.join(", ")}`);
  }
  const body = item.description ?? item.extended ?? "";
  if (body) {
    lines.push("", body);
  }
  return lines.join("\n").trim();
}

function PinboardTab({
  stash,
  onAddToStash,
}: {
  stash: Clip[];
  onAddToStash: (clip: Omit<Clip, "id" | "addedAt">) => void;
}) {
  const [query, setQuery] = useState("");
  const [tag, setTag] = useState("");
  const [results, setResults] = useState<PinboardItem[]>([]);
  const [warning, setWarning] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleSearch(nextQuery: string, nextTag = tag) {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void doSearch(nextQuery, nextTag);
    }, 400);
  }

  async function doSearch(nextQuery: string, nextTag: string) {
    if (!nextQuery.trim() && !nextTag.trim()) {
      setResults([]);
      setWarning(null);
      return;
    }
    setIsSearching(true);
    try {
      const payload = await searchPinboardBookmarks({
        query: nextQuery.trim(),
        tag: nextTag.trim() || undefined,
        top_k: 8,
      });
      setResults(payload.items ?? []);
      setWarning(payload.warning ?? payload.error?.message ?? null);
    } catch (err) {
      setWarning(err instanceof Error ? err.message : "Pinboard search failed");
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  }

  const stashedTitles = new Set(stash.filter((c) => c.source === "pinboard").map((c) => c.title));

  return (
    <div className="space-y-3">
      <div className="grid gap-2">
        <div className="relative">
          <Input
            value={query}
            onChange={(e) => {
              const next = e.target.value;
              setQuery(next);
              handleSearch(next, tag);
            }}
            placeholder="Search Pinboard bookmarks..."
            className="h-8 pr-8 text-sm"
          />
          <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
            {isSearching ? (
              <Loader2Icon className="size-3.5 animate-spin text-muted-foreground" />
            ) : (
              <SearchIcon className="size-3.5 text-muted-foreground" />
            )}
          </div>
        </div>
        <Input
          value={tag}
          onChange={(e) => {
            const next = e.target.value;
            setTag(next);
            handleSearch(query, next);
          }}
          placeholder="Filter by tag (optional)"
          className="h-8 text-sm"
        />
      </div>

      {warning && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
          {warning}
        </div>
      )}

      {results.length > 0 ? (
        <div className="space-y-2">
          {results.map((item, i) => {
            const alreadyStashed = stashedTitles.has(item.title);
            const preview = item.description ?? item.extended ?? item.url;
            return (
              <div key={`${item.url_normalized}-${i}`} className="rounded-lg border bg-muted/30 px-3 py-2 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <SourceBadge source="pinboard" />
                    <div className="mt-1 font-medium leading-snug">{item.title}</div>
                    <div className="mt-1 truncate text-[11px] text-muted-foreground">{item.url}</div>
                    {item.tags.length > 0 && (
                      <div className="mt-1 text-[11px] text-muted-foreground">#{item.tags.join(" #")}</div>
                    )}
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="mt-0.5 h-6 shrink-0 px-2 text-xs"
                    disabled={alreadyStashed}
                    onClick={() => {
                      onAddToStash({
                        source: "pinboard",
                        title: item.title,
                        content: formatPinboardClip(item),
                      });
                    }}
                  >
                    <PlusIcon className="size-3" />
                    {alreadyStashed ? "Added" : "Add"}
                  </Button>
                </div>
                <p className="mt-1 line-clamp-3 text-muted-foreground">{preview}</p>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed px-3 py-4 text-xs text-muted-foreground">
          Search Pinboard bookmarks by text or tag, then stash useful scraps into the desk.
        </div>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function ClipsBoard({ docId, onInsert }: ClipsBoardProps) {
  const [clips, setClips] = useState<Clip[]>(() => loadClips(docId));
  const [activeTab, setActiveTab] = useState<string>("surfsense");

  // Reload when docId changes
  useEffect(() => {
    setClips(loadClips(docId));
  }, [docId]);

  // Persist on every change
  useEffect(() => {
    saveClips(docId, clips);
  }, [docId, clips]);

  function addToStash(partial: Omit<Clip, "id" | "addedAt">) {
    const clip: Clip = {
      ...partial,
      id: crypto.randomUUID(),
      addedAt: Date.now(),
    };
    setClips((prev) => [clip, ...prev]);
    toast.success(`Added "${clip.title}" to stash`);
  }

  function removeFromStash(id: string) {
    setClips((prev) => prev.filter((c) => c.id !== id));
  }

  // Sorted newest first
  const sortedClips = [...clips].sort((a, b) => b.addedAt - a.addedAt);
  const count = clips.length;

  return (
    <div className="flex h-full flex-col gap-3">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-1 flex-col">
        <div className="flex items-center justify-between gap-2 shrink-0">
          <TabsList className="h-8 grid grid-cols-5 flex-1">
            <TabsTrigger value="surfsense" className="text-xs px-1">
              SurfSense
            </TabsTrigger>
            <TabsTrigger value="calibre" className="text-xs px-1">
              Calibre
            </TabsTrigger>
            <TabsTrigger value="pinboard" className="text-xs px-1">
              Pinboard
            </TabsTrigger>
            <TabsTrigger value="chat" className="text-xs px-1">
              Chat
            </TabsTrigger>
            <TabsTrigger value="paste" className="text-xs px-1">
              Paste
            </TabsTrigger>
          </TabsList>
          {count > 0 && (
            <span className="shrink-0 rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-medium text-primary">
              {count}
            </span>
          )}
        </div>

        <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
          <TabsContent value="surfsense" className="mt-0 space-y-3">
            <SurfSenseTab stash={clips} onAddToStash={addToStash} />
          </TabsContent>

          <TabsContent value="calibre" className="mt-0 space-y-3">
            <CalibreTab stash={clips} onAddToStash={addToStash} />
          </TabsContent>

          <TabsContent value="pinboard" className="mt-0 space-y-3">
            <PinboardTab stash={clips} onAddToStash={addToStash} />
          </TabsContent>

          <TabsContent value="chat" className="mt-0 space-y-3">
            <ChatTab stash={clips} onAddToStash={addToStash} />
          </TabsContent>

          <TabsContent value="paste" className="mt-0 space-y-3">
            <PasteTab onAddToStash={addToStash} />
          </TabsContent>

          <StashSection
            clips={sortedClips}
            onInsert={onInsert}
            onRemove={removeFromStash}
          />
        </div>
      </Tabs>
    </div>
  );
}
