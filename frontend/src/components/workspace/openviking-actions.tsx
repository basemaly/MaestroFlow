"use client";

import { Layers3Icon, Loader2Icon, PlusIcon, RefreshCcwIcon, SearchIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
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
import { useWorkspaceContextPacks } from "@/components/workspace/context-packs-context";
import {
  attachOpenVikingContextPacks,
  getOpenVikingConfig,
  searchOpenVikingContextPacks,
  syncOpenVikingContextPacks,
} from "@/core/openviking/api";
import type { OpenVikingConfigResponse, OpenVikingContextPack } from "@/core/openviking/types";

function summarizePack(pack: OpenVikingContextPack) {
  return `${pack.references.length} reference${pack.references.length === 1 ? "" : "s"} · ${pack.skills.length} skill${pack.skills.length === 1 ? "" : "s"} · ${pack.prompts.length} prompt${pack.prompts.length === 1 ? "" : "s"}`;
}

function compactLabel(pack: OpenVikingContextPack) {
  return pack.title || pack.pack_id;
}

export function OpenVikingActions() {
  const { packs, attachPacks } = useWorkspaceContextPacks();
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [sourceKey, setSourceKey] = useState("");
  const [topK, setTopK] = useState("12");
  const [config, setConfig] = useState<OpenVikingConfigResponse | null>(null);
  const [results, setResults] = useState<OpenVikingContextPack[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [loadingConfig, setLoadingConfig] = useState(false);
  const [loadingResults, setLoadingResults] = useState(false);
  const [attaching, setAttaching] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const configAbortRef = useRef<AbortController | null>(null);
  const searchAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }
    const controller = new AbortController();
    configAbortRef.current?.abort();
    configAbortRef.current = controller;
    setLoadingConfig(true);
    void (async () => {
      try {
        const payload = await getOpenVikingConfig();
        if (!controller.signal.aborted) {
          setConfig(payload);
          if (payload.warning) {
            toast.warning(payload.warning);
          }
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          const message = error instanceof Error ? error.message : String(error);
          setConfig({
            base_url: "",
            enabled: false,
            configured: false,
            available: false,
            warning: message,
            error: {
              error_code: "openviking_unavailable",
              message,
            },
          });
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoadingConfig(false);
        }
      }
    })();
    return () => controller.abort();
  }, [open]);

  const activePackIds = useMemo(() => new Set(packs.map((pack) => pack.pack_id)), [packs]);

  async function handleSearch() {
    const trimmedTopK = Math.max(1, Math.min(20, Number.parseInt(topK, 10) || 12));
    searchAbortRef.current?.abort();
    const controller = new AbortController();
    searchAbortRef.current = controller;
    setLoadingResults(true);
    try {
      const payload = await searchOpenVikingContextPacks({
        query: query.trim() || undefined,
        source_key: sourceKey.trim() || undefined,
        top_k: trimmedTopK,
      });
      if (!controller.signal.aborted) {
        setResults(payload.items ?? []);
        setSelected(
          Object.fromEntries((payload.items ?? []).map((pack) => [pack.pack_id, !activePackIds.has(pack.pack_id)])),
        );
        if (payload.warning) {
          toast.warning(payload.warning);
        }
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        toast.error(error instanceof Error ? error.message : String(error));
      }
    } finally {
      if (searchAbortRef.current === controller) {
        searchAbortRef.current = null;
      }
      if (!controller.signal.aborted) {
        setLoadingResults(false);
      }
    }
  }

  async function handleAttach() {
    const selectedPacks = results.filter((pack) => selected[pack.pack_id] !== false);
    if (selectedPacks.length === 0) {
      toast.error("Select at least one pack to attach");
      return;
    }
    setAttaching(true);
    try {
      const payload = await attachOpenVikingContextPacks({
        packs: selectedPacks,
        scope: "workspace",
      });
      attachPacks(payload.items?.length ? payload.items : selectedPacks);
      if (payload.warning) {
        toast.warning(payload.warning);
      }
      toast.success(`Attached ${payload.attached} pack${payload.attached === 1 ? "" : "s"}`);
    } catch (error) {
      attachPacks(selectedPacks);
      toast.warning(`Saved locally: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setAttaching(false);
    }
  }

  async function handleSync() {
    setSyncing(true);
    try {
      const payload = await syncOpenVikingContextPacks({ scope: "workspace" });
      if (payload.warning) {
        toast.warning(payload.warning);
      }
      if (payload.synced > 0) {
        toast.success(`Synced ${payload.synced} pack${payload.synced === 1 ? "" : "s"}`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setSyncing(false);
    }
  }

  if (!mounted) {
    return (
      <Button size="sm" variant="ghost" className="h-8 px-2 text-muted-foreground" disabled>
        <Layers3Icon className="size-4" />
      </Button>
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) {
          setQuery("");
          setSourceKey("");
          setTopK("12");
          setResults([]);
          setSelected({});
        }
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="ghost" className="h-8 px-2 text-muted-foreground" title="Attach OpenViking context packs">
          <Layers3Icon className="size-4" />
          <span className="hidden sm:inline">OpenViking</span>
          <Badge variant="outline" className="ml-1 rounded-full px-1.5 py-0 text-[10px]">
            {packs.length}
          </Badge>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Attach OpenViking Context Packs</DialogTitle>
          <DialogDescription>
            Search reusable packs, attach the ones you want, and keep them available across Composer, chat, and Executive.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="rounded-2xl border border-border/70 bg-muted/20 p-4 text-sm">
            {loadingConfig ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2Icon className="size-4 animate-spin" />
                Loading OpenViking status...
              </div>
            ) : config ? (
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-muted-foreground">Status:</span>
                  <span
                    className={
                      config.configured && config.available
                        ? "rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-emerald-700"
                        : "rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-700"
                    }
                  >
                    {config.configured ? (config.available ? "Connected" : "Unavailable") : "Not configured"}
                  </span>
                </div>
                {config.warning ? (
                  <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-800">
                    {config.warning}
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="text-muted-foreground">OpenViking status unavailable.</div>
            )}
          </div>

          <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
            <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search packs..." />
            <Input value={sourceKey} onChange={(event) => setSourceKey(event.target.value)} placeholder="Source key (optional)" />
            <Button type="button" onClick={() => void handleSearch()} disabled={loadingResults}>
              {loadingResults ? <Loader2Icon className="size-4 animate-spin" /> : <SearchIcon className="size-4" />}
              Search
            </Button>
          </div>

          <div className="flex items-center justify-between gap-3">
            <Input
              value={topK}
              onChange={(event) => setTopK(event.target.value)}
              inputMode="numeric"
              className="max-w-28"
              placeholder="Top K"
            />
            <Button type="button" variant="outline" onClick={() => void handleSync()} disabled={syncing}>
              {syncing ? <Loader2Icon className="size-4 animate-spin" /> : <RefreshCcwIcon className="size-4" />}
              Sync
            </Button>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
            <ScrollArea className="h-[24rem] rounded-2xl border border-border/70">
              <div className="space-y-3 p-4">
                {results.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 p-6 text-sm">
                    <div className="font-medium">No packs loaded</div>
                    <div className="mt-2 text-muted-foreground">Search OpenViking to browse reusable context packs.</div>
                  </div>
                ) : (
                  results.map((pack) => (
                    <label key={pack.pack_id} className="flex items-start gap-3 rounded-2xl border border-border/70 bg-background/70 p-4">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={Boolean(selected[pack.pack_id])}
                        disabled={activePackIds.has(pack.pack_id)}
                        onChange={(event) =>
                          setSelected((current) => ({
                            ...current,
                            [pack.pack_id]: event.target.checked,
                          }))
                        }
                      />
                      <div className="min-w-0 flex-1 space-y-2">
                        <div>
                          <div className="font-medium">{compactLabel(pack)}</div>
                          <div className="text-muted-foreground mt-1 line-clamp-2 text-xs">{pack.description || "Context pack"}</div>
                        </div>
                        <div className="text-muted-foreground text-[11px]">{summarizePack(pack)}</div>
                      </div>
                      {activePackIds.has(pack.pack_id) ? (
                        <Badge variant="outline" className="rounded-full text-[10px]">
                          active
                        </Badge>
                      ) : null}
                    </label>
                  ))
                )}
              </div>
            </ScrollArea>

            <div className="rounded-2xl border border-border/70 bg-muted/10 p-4">
              <div className="text-sm font-medium">Active packs</div>
              <div className="text-muted-foreground mt-1 text-xs">These packs remain attached to the workspace until removed.</div>
              <div className="mt-4 space-y-2">
                {packs.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-border/70 bg-background/70 p-4 text-sm text-muted-foreground">
                    No packs attached yet.
                  </div>
                ) : (
                  packs.map((pack) => (
                    <div key={pack.pack_id} className="rounded-2xl border border-border/70 bg-background/70 p-3">
                      <div className="truncate text-sm font-medium">{pack.title}</div>
                      <div className="text-muted-foreground mt-1 line-clamp-2 text-xs">{pack.description || "Attached context pack"}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          <Button type="button" onClick={() => void handleAttach()} disabled={attaching || results.length === 0}>
            <PlusIcon className="size-4" />
            Attach selected packs
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
