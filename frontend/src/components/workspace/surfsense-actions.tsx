"use client";

import { ExternalLinkIcon, Loader2Icon, SearchIcon, WavesIcon } from "lucide-react";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getBackendBaseURL } from "@/core/config";
import { env } from "@/env";

type SurfSenseConfig = {
  configured: boolean;
  available?: boolean;
  warning?: string | null;
  sync_enabled: boolean;
  default_search_space_id?: number | null;
  resolved_search_space_id?: number | null;
  project_mapping_keys?: string[];
};

type SurfSenseResult = {
  id?: number;
  title: string;
  preview?: string;
  search_space_id?: number;
  document_type?: string;
};

type SurfSenseSearchSpace = {
  id: number;
  name: string;
};

function normalizeSearchSpaces(payload: unknown): SurfSenseSearchSpace[] {
  const rawItems = Array.isArray(payload)
    ? payload
    : Array.isArray((payload as { items?: unknown })?.items)
      ? ((payload as { items: unknown[] }).items ?? [])
      : [];

  return rawItems
    .map((item) => {
      const record = item as Record<string, unknown>;
      return {
        id: typeof record.id === "number" ? record.id : Number.NaN,
        name:
          asText(record.name) ??
          (typeof record.id === "number"
            ? `Search Space ${record.id}`
            : "Untitled Search Space"),
      };
    })
    .filter((item) => Number.isFinite(item.id));
}

function asText(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function normalizeResults(payload: unknown): SurfSenseResult[] {
  const arraysToTry = [
    payload,
    (payload as { items?: unknown })?.items,
    (payload as { results?: unknown })?.results,
    (payload as { documents?: unknown })?.documents,
    (payload as { data?: { items?: unknown; results?: unknown } })?.data?.items,
    (payload as { data?: { items?: unknown; results?: unknown } })?.data?.results,
  ];
  const rawItems = arraysToTry.find(Array.isArray) as Array<Record<string, unknown>> | undefined;
  if (!rawItems) {
    return [];
  }
  return rawItems.map((item) => ({
    id: typeof item.id === "number" ? item.id : undefined,
    title:
      asText(item.title) ??
      asText(item.name) ??
      asText(item.document_title) ??
      asText(item.filename) ??
      "Untitled",
    preview:
      (
        asText(item.preview) ??
        asText(item.snippet) ??
        asText(item.summary) ??
        asText(item.content_preview) ??
        asText(item.source_markdown) ??
        ""
      ).trim() || undefined,
    search_space_id:
      typeof item.search_space_id === "number" ? item.search_space_id : undefined,
    document_type:
      typeof item.document_type === "string" ? item.document_type : undefined,
  }));
}

function getSurfSenseLink(baseUrl: string, result: SurfSenseResult): string {
  if (result.search_space_id && result.id && result.document_type !== "REPORT") {
    return `${baseUrl}/dashboard/${result.search_space_id}/editor/${result.id}`;
  }
  if (result.search_space_id) {
    return `${baseUrl}/dashboard/${result.search_space_id}/new-chat`;
  }
  return baseUrl;
}

function getSafeSurfSenseBaseUrl(rawBaseUrl: string | undefined): string {
  try {
    const parsed = new URL(rawBaseUrl?.trim() ?? "http://localhost:3004");
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return "http://localhost:3004";
    }
    parsed.pathname = "";
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return "http://localhost:3004";
  }
}

function describeSearchSpace(
  id: number | null | undefined,
  searchSpaceNameById: Map<number, string>,
): string {
  if (!id) {
    return "None";
  }
  return searchSpaceNameById.get(id) ?? `Space ${id}`;
}

function SurfSenseActionsComponent() {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [projectKey, setProjectKey] = useState("");
  const [searchSpaceId, setSearchSpaceId] = useState("");
  const [config, setConfig] = useState<SurfSenseConfig | null>(null);
  const [searchSpaces, setSearchSpaces] = useState<SurfSenseSearchSpace[]>([]);
  const [results, setResults] = useState<SurfSenseResult[]>([]);
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const configAbortRef = useRef<AbortController | null>(null);
  const searchAbortRef = useRef<AbortController | null>(null);

  const surfSenseBaseUrl = useMemo(
    () => getSafeSurfSenseBaseUrl(env.NEXT_PUBLIC_SURFSENSE_BASE_URL),
    [],
  );
  const searchSpaceNameById = useMemo(
    () => new Map(searchSpaces.map((space) => [space.id, space.name])),
    [searchSpaces],
  );
  const resolvedSearchSpaceId = useMemo(() => {
    const parsed = Number.parseInt(searchSpaceId, 10);
    return Number.isNaN(parsed) ? undefined : parsed;
  }, [searchSpaceId]);

  useEffect(() => {
    setMounted(true);
  }, []);

  async function handleSearch() {
    if (!query.trim()) {
      toast.error("Enter a SurfSense search query first");
      return;
    }
    searchAbortRef.current?.abort();
    const controller = new AbortController();
    searchAbortRef.current = controller;
    setIsSearching(true);
    try {
      const response = await fetch(`${getBackendBaseURL()}/api/surfsense/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          query: query.trim(),
          project_key: projectKey.trim() || undefined,
          search_space_id: resolvedSearchSpaceId,
          top_k: 8,
        }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(payload.detail ?? "SurfSense search failed");
      }
      const payload = (await response.json()) as { warning?: string } & unknown;
      if (payload && typeof payload === "object" && typeof payload.warning === "string" && payload.warning) {
        toast.warning(payload.warning);
      }
      setResults(normalizeResults(payload));
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      if (searchAbortRef.current === controller) {
        searchAbortRef.current = null;
      }
      setIsSearching(false);
    }
  }

  useEffect(() => {
    if (!open) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      configAbortRef.current?.abort();
      const controller = new AbortController();
      configAbortRef.current = controller;
      setIsLoadingConfig(true);
      void (async () => {
        try {
          const response = await fetch(
            `${getBackendBaseURL()}/api/surfsense/config${projectKey.trim() ? `?project_key=${encodeURIComponent(projectKey.trim())}` : ""}`,
            { signal: controller.signal },
          );
          if (!response.ok) {
            throw new Error("Failed to load SurfSense integration status");
          }
          const payload = (await response.json()) as SurfSenseConfig;
          const spacesResponse = await fetch(`${getBackendBaseURL()}/api/surfsense/search-spaces`, {
            signal: controller.signal,
          });
          const spacesPayload = spacesResponse.ok ? await spacesResponse.json() : null;
          const nextSearchSpaces = normalizeSearchSpaces(spacesPayload);

          setConfig(payload);
          setSearchSpaces(nextSearchSpaces);
          setSearchSpaceId((currentValue) =>
            {
              const currentId = Number.parseInt(currentValue, 10);
              if (
                currentValue &&
                !Number.isNaN(currentId) &&
                nextSearchSpaces.some((space) => space.id === currentId)
              ) {
                return currentValue;
              }
              if (
                payload.resolved_search_space_id &&
                nextSearchSpaces.some((space) => space.id === payload.resolved_search_space_id)
              ) {
                return String(payload.resolved_search_space_id);
              }
              if (nextSearchSpaces.length === 1) {
                return String(nextSearchSpaces[0]!.id);
              }
              return "";
            },
          );
        } catch (error) {
          if (controller.signal.aborted) {
            return;
          }
          toast.error(error instanceof Error ? error.message : String(error));
        } finally {
          if (configAbortRef.current === controller) {
            configAbortRef.current = null;
          }
          setIsLoadingConfig(false);
        }
      })();
    }, 250);
    return () => window.clearTimeout(timeoutId);
  }, [open, projectKey]);

  useEffect(() => {
    return () => {
      configAbortRef.current?.abort();
      searchAbortRef.current?.abort();
    };
  }, []);

  const canSearch = query.trim().length > 0 && !isSearching;
  const hasResults = results.length > 0;
  const trimmedProjectKey = projectKey.trim();

  return (
    <div className="flex items-center gap-1">
      <Button
        size="sm"
        variant="ghost"
        className="h-8 px-2 text-muted-foreground"
        title="Open SurfSense dashboard — browse search spaces, manage documents, and review notes in the SurfSense web interface."
        asChild
      >
        <a href={surfSenseBaseUrl} target="_blank" rel="noreferrer">
          <WavesIcon className="size-4" />
          <span className="hidden sm:inline">SurfSense</span>
        </a>
      </Button>
      {!mounted ? (
        <Button
          size="sm"
          variant="ghost"
          className="h-8 px-2 text-muted-foreground"
          disabled
        >
          <SearchIcon className="size-4" />
        </Button>
      ) : (
      <Dialog
        open={open}
        onOpenChange={(nextOpen) => {
          setOpen(nextOpen);
          if (!nextOpen) {
            configAbortRef.current?.abort();
            searchAbortRef.current?.abort();
            setQuery("");
            setResults([]);
            setShowAdvanced(false);
          }
        }}
      >
        <DialogTrigger asChild>
          <Button size="sm" variant="ghost" className="h-8 px-2 text-muted-foreground" title="Search SurfSense — find documents, notes, and reports across your search spaces. Results open directly in SurfSense.">
            <SearchIcon className="size-4" />
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Search SurfSense Documents</DialogTitle>
            <DialogDescription>
              Search documents, notes, and reports stored in your SurfSense search spaces before branching into deeper research or editing.
            </DialogDescription>
          </DialogHeader>
          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (canSearch) {
                void handleSearch();
              }
            }}
          >
            <div className="rounded-2xl border border-border/70 bg-muted/20 p-4 text-sm">
              {isLoadingConfig ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2Icon className="size-4 animate-spin" />
                  Loading integration status...
                </div>
              ) : config ? (
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-muted-foreground">Status:</span>
                    <span
                      className={
                        config.configured && config.available !== false
                          ? "rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-emerald-700"
                          : "rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-700"
                      }
                    >
                      {config.configured
                        ? config.available === false
                          ? "Unavailable"
                          : "Connected"
                        : "Token Missing"}
                    </span>
                    <span className="text-muted-foreground text-xs">
                      Sync {config.sync_enabled ? "enabled" : "disabled"}
                    </span>
                  </div>
                  {config.warning && (
                    <div className="text-amber-700 text-xs">{config.warning}</div>
                  )}
                  <div className="text-muted-foreground text-xs">
                    Default space: {describeSearchSpace(config.default_search_space_id, searchSpaceNameById)} · Resolved space:{" "}
                    {describeSearchSpace(config.resolved_search_space_id, searchSpaceNameById)}
                  </div>
                  {!!config.warning && (
                    <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-amber-800">
                      {config.warning}
                    </div>
                  )}
                  {!!config.project_mapping_keys?.length && (
                    <div className="text-muted-foreground text-xs">
                      Mapped keys: {config.project_mapping_keys.join(", ")}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-muted-foreground">SurfSense status unavailable.</div>
              )}
            </div>
            <div className="grid gap-3 md:grid-cols-[1.2fr_0.8fr]">
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search document titles and contents..."
                  autoCapitalize="off"
                  autoCorrect="off"
                />
              <Select value={searchSpaceId || "__all__"} onValueChange={(value) => setSearchSpaceId(value === "__all__" ? "" : value)}>
                <SelectTrigger className="w-full bg-background">
                  <SelectValue placeholder="Choose a SurfSense space" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All accessible SurfSense spaces</SelectItem>
                  {searchSpaces.map((space) => (
                    <SelectItem key={space.id} value={String(space.id)}>
                      {space.name} (#{space.id})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between gap-3 text-xs">
              <div className="text-muted-foreground">
                {searchSpaces.length
                  ? "Search spaces shown here are the ones your SurfSense integration token can actually access."
                  : "No accessible SurfSense search spaces were returned. Search will fall back to any token-visible content."}
              </div>
              {!!config?.project_mapping_keys?.length && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="rounded-full px-3"
                  onClick={() => setShowAdvanced((current) => !current)}
                >
                  {showAdvanced ? "Hide advanced" : "Show advanced"}
                </Button>
              )}
            </div>
            {showAdvanced && (
              <div className="grid gap-2 rounded-2xl border border-border/70 bg-muted/10 p-4">
                <div className="text-sm font-medium">Project Key</div>
                <Input
                  value={projectKey}
                  onChange={(event) => setProjectKey(event.target.value)}
                  placeholder="Optional mapped key, if your setup uses one"
                  autoCapitalize="off"
                  autoCorrect="off"
                />
                <div className="text-muted-foreground text-xs">
                  Project keys are optional aliases defined in MaestroFlow. Most of the time, choosing a named SurfSense search space above is simpler.
                </div>
              </div>
            )}
            <div className="flex items-center justify-between gap-3">
              <div className="text-muted-foreground text-xs">
                Search by named SurfSense space when possible.
                {trimmedProjectKey ? ` Advanced key: ${trimmedProjectKey}.` : ""}
              </div>
              <Button
                type="submit"
                className="rounded-full border-2 border-transparent px-5"
                disabled={!canSearch}
              >
                {isSearching ? <Loader2Icon className="size-4 animate-spin" /> : <SearchIcon className="size-4" />}
                Run Search
              </Button>
            </div>
            <ScrollArea className="h-[24rem] rounded-2xl border border-border/70">
              <div className="space-y-3 p-4">
                {!hasResults ? (
                  <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 p-6 text-sm">
                    <div className="font-medium">
                      {isSearching ? "Searching SurfSense documents..." : "No results yet"}
                    </div>
                    <div className="text-muted-foreground mt-2">
                      {query.trim()
                        ? "Try a broader query or switch to a different named SurfSense space."
                        : "Enter a query to search notes, documents, and reports from SurfSense."}
                    </div>
                  </div>
                ) : (
                  results.map((result, index) => (
                    <div
                      key={`${result.id ?? "result"}-${index}`}
                      className="rounded-2xl border border-border/70 bg-background/70 p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-medium">{result.title}</div>
                          <div className="text-muted-foreground mt-1 text-xs">
                            {result.document_type ?? "Document"}
                            {result.search_space_id
                              ? ` · ${searchSpaceNameById.get(result.search_space_id) ?? `Space ${result.search_space_id}`}`
                              : ""}
                          </div>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-full border-2"
                          asChild
                        >
                          <a
                            href={getSurfSenseLink(surfSenseBaseUrl, result)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <ExternalLinkIcon className="size-4" />
                            Open
                          </a>
                        </Button>
                      </div>
                      {result.preview && (
                        <div className="text-muted-foreground mt-3 text-sm">
                          {result.preview.length > 280
                            ? `${result.preview.slice(0, 280)}...`
                            : result.preview}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </form>
        </DialogContent>
      </Dialog>
      )}
    </div>
  );
}

export const SurfSenseActions = memo(SurfSenseActionsComponent);
