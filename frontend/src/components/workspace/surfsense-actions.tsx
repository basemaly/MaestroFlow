"use client";

import { ExternalLinkIcon, Loader2Icon, SearchIcon, WavesIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
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
import { getBackendBaseURL } from "@/core/config";
import { env } from "@/env";

type SurfSenseConfig = {
  configured: boolean;
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

export function SurfSenseActions() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [projectKey, setProjectKey] = useState("");
  const [searchSpaceId, setSearchSpaceId] = useState("");
  const [config, setConfig] = useState<SurfSenseConfig | null>(null);
  const [results, setResults] = useState<SurfSenseResult[]>([]);
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const configAbortRef = useRef<AbortController | null>(null);
  const searchAbortRef = useRef<AbortController | null>(null);

  const surfSenseBaseUrl = useMemo(
    () => getSafeSurfSenseBaseUrl(env.NEXT_PUBLIC_SURFSENSE_BASE_URL),
    [],
  );
  const resolvedSearchSpaceId = useMemo(() => {
    const parsed = Number.parseInt(searchSpaceId, 10);
    return Number.isNaN(parsed) ? undefined : parsed;
  }, [searchSpaceId]);

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
      const payload = (await response.json()) as unknown;
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
          setConfig(payload);
          setSearchSpaceId((currentValue) =>
            !currentValue && payload.resolved_search_space_id
              ? String(payload.resolved_search_space_id)
              : currentValue,
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

  return (
    <div className="flex items-center gap-2">
      <Button
        size="sm"
        variant="outline"
        className="rounded-full border-2 px-4"
        asChild
      >
        <a href={surfSenseBaseUrl} target="_blank" rel="noreferrer">
          <WavesIcon className="size-4" />
          Open SurfSense
        </a>
      </Button>
      <Dialog
        open={open}
        onOpenChange={(nextOpen) => {
          setOpen(nextOpen);
          if (!nextOpen) {
            configAbortRef.current?.abort();
            searchAbortRef.current?.abort();
          }
        }}
      >
        <DialogTrigger asChild>
          <Button size="sm" variant="outline" className="rounded-full border-2 px-4">
            <SearchIcon className="size-4" />
            Search SurfSense
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>SurfSense Search</DialogTitle>
            <DialogDescription>
              Query your SurfSense knowledge base from inside MaestroFlow before you branch into deeper research or editing.
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
                        config.configured
                          ? "rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-emerald-700"
                          : "rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-700"
                      }
                    >
                      {config.configured ? "Connected" : "Token Missing"}
                    </span>
                    <span className="text-muted-foreground text-xs">
                      Sync {config.sync_enabled ? "enabled" : "disabled"}
                    </span>
                  </div>
                  <div className="text-muted-foreground text-xs">
                    Default search space: {config.default_search_space_id ?? "None"} · Resolved search space:{" "}
                    {config.resolved_search_space_id ?? "None"}
                  </div>
                </div>
              ) : (
                <div className="text-muted-foreground">SurfSense status unavailable.</div>
              )}
            </div>
            <div className="grid gap-3 md:grid-cols-[1.3fr_0.7fr]">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search notes, documents, or reports..."
                autoCapitalize="off"
                autoCorrect="off"
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  value={projectKey}
                  onChange={(event) => setProjectKey(event.target.value)}
                  placeholder="Project key"
                  autoCapitalize="off"
                  autoCorrect="off"
                />
                <Input
                  value={searchSpaceId}
                  onChange={(event) => setSearchSpaceId(event.target.value.replace(/[^\d]/g, ""))}
                  placeholder="Search space ID"
                  inputMode="numeric"
                />
              </div>
            </div>
            <div className="flex items-center justify-between gap-3">
              <div className="text-muted-foreground text-xs">
                Use a mapped project key for stable routing, or a specific search space ID for one-off lookup.
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
                {results.length === 0 ? (
                  <div className="text-muted-foreground text-sm">
                    {isSearching ? "Searching SurfSense..." : "No results yet."}
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
                            {result.search_space_id ? ` · Space ${result.search_space_id}` : ""}
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
    </div>
  );
}
