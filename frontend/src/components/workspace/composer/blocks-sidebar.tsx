"use client";

import {
  ChevronRightIcon,
  ClipboardCopyIcon,
  FilePlusIcon,
  XIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { BlockEditorHandle } from "@/components/workspace/block-editor/block-editor";
import type { CollageBlock } from "@/core/documents/collage-blocks";
import { loadBlocks, removeBlock } from "@/core/documents/collage-blocks";
import { cn } from "@/lib/utils";

const SOURCE_DOT: Record<string, string> = {
  surfsense: "bg-blue-400",
  calibre: "bg-amber-400",
  chat: "bg-violet-400",
  pasted: "bg-green-400",
  manual: "bg-zinc-400",
  pinboard: "bg-rose-400",
};

const SOURCE_LABELS: Record<string, string> = {
  surfsense: "SurfSense",
  calibre: "Calibre",
  chat: "Chat",
  pasted: "Pasted",
  manual: "Manual",
  pinboard: "Pinboard",
};

export function BlocksSidebar({
  docId,
  editorHandleRef,
  onSwitchToCollage,
}: {
  docId: string;
  editorHandleRef: React.MutableRefObject<BlockEditorHandle | null>;
  onSwitchToCollage: () => void;
}) {
  const [blocks, setBlocks] = useState<CollageBlock[]>(() => loadBlocks(docId));
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  // Refresh blocks when the sidebar becomes visible or when the doc changes
  useEffect(() => {
    const refresh = () => setBlocks(loadBlocks(docId));
    // Poll every 2s — lightweight since it's just a localStorage read
    const id = setInterval(refresh, 2000);
    refresh();
    return () => clearInterval(id);
  }, [docId]);

  function toggleExpanded(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function handleInsert(block: CollageBlock) {
    const handle = editorHandleRef.current;
    if (!handle) {
      toast.error("Editor not ready — try again in a moment");
      return;
    }
    handle.insertMarkdown(`\n\n${block.content}\n\n`);
    toast.success("Inserted into document");
  }

  function handleCopy(block: CollageBlock) {
    void navigator.clipboard.writeText(block.content).then(
      () => toast.success("Copied"),
      () => toast.error("Copy failed"),
    );
  }

  function handleRemove(block: CollageBlock) {
    const updated = removeBlock(docId, block.id);
    setBlocks(updated);
  }

  const wc = (text: string) => text.trim().split(/\s+/).filter(Boolean).length;

  return (
    <div className="flex h-full w-72 shrink-0 flex-col rounded-3xl border border-border/70 bg-background/92 shadow-sm">
      <div className="shrink-0 border-b border-border/70 px-3 py-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
              Collected
            </div>
            <div className="mt-0.5 text-sm font-medium">
              Blocks
              {blocks.length > 0 && (
                <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-normal">
                  {blocks.length}
                </span>
              )}
            </div>
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 gap-1 text-xs"
            onClick={onSwitchToCollage}
            title="Open Collage view"
          >
            <FilePlusIcon className="size-3" />
            <span className="hidden sm:inline">Collage</span>
          </Button>
        </div>
        <div className="mt-1 text-[10px] text-muted-foreground">
          Insert any block into the editor at cursor, or switch to Collage to arrange and stitch.
        </div>
      </div>
      <ScrollArea className="flex-1">
        {blocks.length === 0 ? (
          <div className="px-3 py-8 text-center text-xs text-muted-foreground">
            <p>No blocks yet.</p>
            <p className="mt-1">Open Collage to pull in fragments from your sources.</p>
          </div>
        ) : (
          <div className="space-y-2 p-3">
            {blocks.map((block) => {
              const expanded = expandedIds.has(block.id);
              const preview = block.content.slice(0, 160);
              return (
                <div
                  key={block.id}
                  className="rounded-2xl border border-border/70 bg-background/80 p-2.5 text-xs shadow-sm"
                >
                  <div className="flex items-start gap-2">
                    <span
                      className={cn("mt-1 size-2 shrink-0 rounded-full", SOURCE_DOT[block.source] ?? "bg-zinc-400")}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium leading-snug">{block.title}</div>
                      <div className="text-[10px] text-muted-foreground">
                        {SOURCE_LABELS[block.source] ?? block.source} · {wc(block.content)}w
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-0.5">
                      <button
                        type="button"
                        onClick={() => toggleExpanded(block.id)}
                        className="rounded p-0.5 text-muted-foreground hover:text-foreground"
                        title={expanded ? "Collapse" : "Preview"}
                      >
                        <ChevronRightIcon
                          className={cn("size-3.5 transition-transform", expanded && "rotate-90")}
                        />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleCopy(block)}
                        className="rounded p-0.5 text-muted-foreground hover:text-foreground"
                        title="Copy content"
                      >
                        <ClipboardCopyIcon className="size-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemove(block)}
                        className="rounded p-0.5 text-muted-foreground hover:text-destructive"
                        title="Remove"
                      >
                        <XIcon className="size-3.5" />
                      </button>
                    </div>
                  </div>

                  {expanded && (
                    <div className="mt-2 rounded-lg border border-border/50 bg-muted/20 p-2">
                      <p className="whitespace-pre-wrap text-[10px] text-muted-foreground">
                        {preview}
                        {block.content.length > 160 && "…"}
                      </p>
                    </div>
                  )}

                  <Button
                    size="sm"
                    variant="ghost"
                    className="mt-1.5 h-6 w-full text-[10px]"
                    onClick={() => handleInsert(block)}
                  >
                    Insert at cursor
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
