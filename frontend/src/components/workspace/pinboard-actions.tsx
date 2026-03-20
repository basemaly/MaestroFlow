"use client";

import { BookmarkIcon, Loader2Icon, UploadIcon } from "lucide-react";
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
import { getPinboardConfig, importPinboardBookmarks, previewPinboardImport } from "@/core/pinboard/api";
import type { PinboardConfigResponse, PinboardPreviewImportResponse } from "@/core/pinboard/types";

function formatDate(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function PinboardActions() {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [tag, setTag] = useState("");
  const [projectKey, setProjectKey] = useState("");
  const [config, setConfig] = useState<PinboardConfigResponse | null>(null);
  const [preview, setPreview] = useState<PinboardPreviewImportResponse | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [loadingConfig, setLoadingConfig] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [importing, setImporting] = useState(false);
  const configAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    configAbortRef.current = controller;
    setLoadingConfig(true);
    void (async () => {
      try {
        const payload = await getPinboardConfig();
        if (!controller.signal.aborted) {
          setConfig(payload);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          toast.error(error instanceof Error ? error.message : String(error));
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoadingConfig(false);
        }
      }
    })();
    return () => controller.abort();
  }, [open]);

  const selectedBookmarks = useMemo(() => {
    const items = preview?.items ?? [];
    return items.filter((item) => selected[item.url_normalized]);
  }, [preview, selected]);

  async function handlePreview() {
    const trimmedQuery = query.trim();
    const trimmedTag = tag.trim();
    const trimmedProjectKey = projectKey.trim();
    setLoadingPreview(true);
    try {
      const payload = await previewPinboardImport({
        query: trimmedQuery.length > 0 ? trimmedQuery : undefined,
        tag: trimmedTag.length > 0 ? trimmedTag : undefined,
        project_key: trimmedProjectKey.length > 0 ? trimmedProjectKey : undefined,
        top_k: 20,
      });
      setPreview(payload);
      setSelected(
        Object.fromEntries(
          (payload.items ?? [])
            .filter((item) => !item.already_imported)
            .map((item) => [item.url_normalized, true]),
        ),
      );
      if (payload.warning) {
        toast.warning(payload.warning);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoadingPreview(false);
    }
  }

  async function handleImport() {
    const trimmedProjectKey = projectKey.trim();
    if (!selectedBookmarks.length) {
      toast.error("Select at least one bookmark to import");
      return;
    }
    setImporting(true);
    try {
      const payload = await importPinboardBookmarks({
        bookmarks: selectedBookmarks,
        project_key: trimmedProjectKey.length > 0 ? trimmedProjectKey : undefined,
      });
      if (payload.failed > 0) {
        toast.warning(`Imported ${payload.imported}, skipped ${payload.skipped}, failed ${payload.failed}`);
      } else {
        toast.success(`Imported ${payload.imported} bookmarks into SurfSense`);
      }
      if (preview) {
        await handlePreview();
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setImporting(false);
    }
  }

  if (!mounted) {
    return (
      <Button size="sm" variant="ghost" className="h-8 px-2 text-muted-foreground" disabled>
        <BookmarkIcon className="size-4" />
      </Button>
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) {
          configAbortRef.current?.abort();
          setPreview(null);
          setSelected({});
          setQuery("");
          setTag("");
          setProjectKey("");
        }
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="ghost" className="h-8 px-2 text-muted-foreground" title="Pinboard — browse, search, and import bookmarks from your Pinboard account into SurfSense for long-term knowledge.">
          <BookmarkIcon className="size-4" />
          <span className="hidden sm:inline">Pinboard</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Import Pinboard Bookmarks</DialogTitle>
          <DialogDescription>
            Search or pull recent bookmarks, preview what is already in SurfSense, then import the pieces you want into the current knowledge lane.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="rounded-2xl border border-border/70 bg-muted/20 p-4 text-sm">
            {loadingConfig ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2Icon className="size-4 animate-spin" />
                Loading Pinboard status...
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
                    {config.configured ? (config.available ? "Connected" : "Unavailable") : "Token Missing"}
                  </span>
                </div>
                {config.warning && (
                  <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-800">
                    {config.warning}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-muted-foreground">Pinboard status unavailable.</div>
            )}
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search bookmarks..."
            />
            <Input
              value={tag}
              onChange={(event) => setTag(event.target.value)}
              placeholder="Tag (optional)"
            />
            <Input
              value={projectKey}
              onChange={(event) => setProjectKey(event.target.value)}
              placeholder="Project key (optional)"
            />
          </div>

          <div className="flex items-center justify-between gap-3">
            <div className="text-xs text-muted-foreground">
              Preview resolves duplicates against the target SurfSense space before writing anything.
            </div>
            <Button type="button" onClick={() => void handlePreview()} disabled={loadingPreview}>
              {loadingPreview ? <Loader2Icon className="size-4 animate-spin" /> : <BookmarkIcon className="size-4" />}
              Preview Import
            </Button>
          </div>

          {preview && (
            <div className="rounded-2xl border border-border/70 bg-muted/10 p-4 text-xs">
              <div className="font-medium">
                {preview.summary?.new_items ?? 0} new · {preview.summary?.already_imported ?? 0} already imported
              </div>
              <div className="mt-1 text-muted-foreground">
                Target lane: {preview.target_search_space_id ? `SurfSense space #${preview.target_search_space_id}` : "Not resolved"}
              </div>
              {preview.warning && <div className="mt-2 text-amber-700">{preview.warning}</div>}
            </div>
          )}

          <ScrollArea className="h-[24rem] rounded-2xl border border-border/70">
            <div className="space-y-3 p-4">
              {!preview?.items?.length ? (
                <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 p-6 text-sm">
                  <div className="font-medium">No preview loaded</div>
                  <div className="mt-2 text-muted-foreground">
                    Search Pinboard or fetch recent bookmarks, then preview before importing.
                  </div>
                </div>
              ) : (
                preview.items.map((item) => (
                  <label
                    key={item.url_normalized}
                    className="flex items-start gap-3 rounded-2xl border border-border/70 bg-background/70 p-4"
                  >
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={Boolean(selected[item.url_normalized])}
                      disabled={(item.already_imported ?? false) || !preview.can_import}
                      onChange={(event) =>
                        setSelected((current) => ({
                          ...current,
                          [item.url_normalized]: event.target.checked,
                        }))
                      }
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="font-medium">{item.title}</div>
                        {item.already_imported ? (
                          <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                            Already imported
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-1 break-all text-muted-foreground">{item.url}</div>
                      {item.tags.length > 0 && (
                        <div className="mt-1 text-muted-foreground">#{item.tags.join(" #")}</div>
                      )}
                      {(item.description || item.extended) && (
                        <div className="mt-2 text-sm text-muted-foreground">
                          {item.description ?? item.extended}
                        </div>
                      )}
                      {formatDate(item.created_at) && (
                        <div className="mt-2 text-[11px] text-muted-foreground">Saved {formatDate(item.created_at)}</div>
                      )}
                    </div>
                  </label>
                ))
              )}
            </div>
          </ScrollArea>

          <div className="flex items-center justify-between gap-3">
            <div className="text-xs text-muted-foreground">
              {selectedBookmarks.length} selected for import
            </div>
            <Button
              type="button"
              onClick={() => void handleImport()}
              disabled={!preview?.can_import || importing || selectedBookmarks.length === 0}
            >
              {importing ? <Loader2Icon className="size-4 animate-spin" /> : <UploadIcon className="size-4" />}
              Import to SurfSense
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
