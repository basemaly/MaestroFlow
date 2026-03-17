"use client";

import {
  BookmarkIcon,
  ClipboardCopyIcon,
  PlusIcon,
  TagIcon,
  Trash2Icon,
  XIcon,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { useSnippets } from "@/core/snippets";
import { cn } from "@/lib/utils";

function SnippetCard({
  snippet,
  onCopy,
  onRemove,
  onUpdateTags,
}: {
  snippet: { id: string; text: string; label: string; tags: string[]; created_at: number };
  onCopy: (text: string) => void;
  onRemove: (id: string) => void;
  onUpdateTags: (id: string, tags: string[]) => void;
}) {
  const [showTagInput, setShowTagInput] = useState(false);
  const [tagDraft, setTagDraft] = useState("");

  const handleAddTag = () => {
    const tag = tagDraft.trim().toLowerCase();
    if (tag && !snippet.tags.includes(tag)) {
      onUpdateTags(snippet.id, [...snippet.tags, tag]);
    }
    setTagDraft("");
    setShowTagInput(false);
  };

  const handleRemoveTag = (tag: string) => {
    onUpdateTags(
      snippet.id,
      snippet.tags.filter((t) => t !== tag),
    );
  };

  return (
    <div className="group rounded-lg border border-border/70 bg-background/80 p-3 transition-colors hover:border-border">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1 text-xs font-medium text-foreground truncate">
          {snippet.label}
        </div>
        <div className="flex shrink-0 gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <Button
            size="icon"
            variant="ghost"
            className="size-6"
            onClick={() => onCopy(snippet.text)}
            title="Copy to clipboard"
          >
            <ClipboardCopyIcon className="size-3.5" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="size-6"
            onClick={() => setShowTagInput(true)}
            title="Add tag"
          >
            <TagIcon className="size-3.5" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="size-6 text-destructive/70 hover:text-destructive"
            onClick={() => onRemove(snippet.id)}
            title="Delete snippet"
          >
            <Trash2Icon className="size-3.5" />
          </Button>
        </div>
      </div>
      <div className="mb-2 max-h-24 overflow-hidden rounded border bg-muted/30 p-2 text-xs leading-5 text-muted-foreground whitespace-pre-wrap">
        {snippet.text.length > 300 ? `${snippet.text.slice(0, 300)}...` : snippet.text}
      </div>
      {snippet.tags.length > 0 && (
        <div className="mb-1.5 flex flex-wrap gap-1">
          {snippet.tags.map((tag) => (
            <Badge
              key={tag}
              variant="secondary"
              className="cursor-pointer gap-1 text-[10px]"
              onClick={() => handleRemoveTag(tag)}
            >
              {tag}
              <XIcon className="size-2.5" />
            </Badge>
          ))}
        </div>
      )}
      {showTagInput && (
        <div className="flex gap-1">
          <Input
            className="h-6 text-xs"
            value={tagDraft}
            onChange={(e) => setTagDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAddTag();
              if (e.key === "Escape") setShowTagInput(false);
            }}
            placeholder="Tag name..."
            autoFocus
          />
          <Button size="sm" className="h-6 px-2 text-xs" onClick={handleAddTag}>
            Add
          </Button>
        </div>
      )}
      <div className="text-[10px] text-muted-foreground/60">
        {new Date(snippet.created_at).toLocaleDateString()}
      </div>
    </div>
  );
}

/** Inner content of the Snippet Shelf — can be used inside any Sheet. */
export function SnippetShelfContent() {
  const { snippets, addSnippet, removeSnippet, updateSnippet, clearAll } = useSnippets();
  const [isAdding, setIsAdding] = useState(false);
  const [draft, setDraft] = useState("");
  const [draftLabel, setDraftLabel] = useState("");
  const [filterTag, setFilterTag] = useState<string | null>(null);

  const allTags = useMemo(() => {
    const set = new Set<string>();
    for (const s of snippets) {
      for (const t of s.tags) set.add(t);
    }
    return Array.from(set).sort();
  }, [snippets]);

  const filtered = useMemo(
    () => (filterTag ? snippets.filter((s) => s.tags.includes(filterTag)) : snippets),
    [snippets, filterTag],
  );

  const handleCopy = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Failed to copy");
    }
  }, []);

  const handleSave = () => {
    if (!draft.trim()) return;
    addSnippet(draft.trim(), draftLabel.trim() || undefined);
    setDraft("");
    setDraftLabel("");
    setIsAdding(false);
    toast.success("Snippet saved");
  };

  const handleUpdateTags = useCallback(
    (id: string, tags: string[]) => {
      updateSnippet(id, { tags });
    },
    [updateSnippet],
  );

  return (
    <>
      <SheetHeader>
        <SheetTitle className="flex items-center gap-2">
          <BookmarkIcon className="size-4" />
          Snippet Shelf
        </SheetTitle>
        <SheetDescription>
          Save and reuse text across threads and workflows.
        </SheetDescription>
      </SheetHeader>

      <div className="flex items-center gap-2 border-b pb-3">
        <Button
          size="sm"
          variant={isAdding ? "secondary" : "outline"}
          className="gap-1"
          onClick={() => setIsAdding(!isAdding)}
        >
          <PlusIcon className="size-3.5" />
          {isAdding ? "Cancel" : "New"}
        </Button>
        {snippets.length > 0 && (
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto text-xs text-destructive/70 hover:text-destructive"
            onClick={() => {
              clearAll();
              toast.success("All snippets cleared");
            }}
          >
            Clear All
          </Button>
        )}
      </div>

      {isAdding && (
        <div className="space-y-2 border-b pb-3">
          <Input
            className="h-8 text-sm"
            placeholder="Label (optional)"
            value={draftLabel}
            onChange={(e) => setDraftLabel(e.target.value)}
          />
          <Textarea
            className="min-h-[100px] resize-none text-sm"
            placeholder="Paste or type snippet text..."
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <Button size="sm" className="w-full" onClick={handleSave} disabled={!draft.trim()}>
            Save Snippet
          </Button>
        </div>
      )}

      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-1 border-b pb-2">
          <Badge
            variant={filterTag === null ? "default" : "outline"}
            className="cursor-pointer text-[10px]"
            onClick={() => setFilterTag(null)}
          >
            All
          </Badge>
          {allTags.map((tag) => (
            <Badge
              key={tag}
              variant={filterTag === tag ? "default" : "outline"}
              className="cursor-pointer text-[10px]"
              onClick={() => setFilterTag(filterTag === tag ? null : tag)}
            >
              {tag}
            </Badge>
          ))}
        </div>
      )}

      <ScrollArea className="flex-1">
        <div className="space-y-2 pr-2">
          {filtered.length === 0 && (
            <div className={cn("py-8 text-center text-sm text-muted-foreground")}>
              {snippets.length === 0
                ? "No snippets yet. Click New to save one."
                : "No snippets match this tag."}
            </div>
          )}
          {filtered.map((snippet) => (
            <SnippetCard
              key={snippet.id}
              snippet={snippet}
              onCopy={handleCopy}
              onRemove={removeSnippet}
              onUpdateTags={handleUpdateTags}
            />
          ))}
        </div>
      </ScrollArea>
    </>
  );
}

/** Header button trigger + Sheet wrapper — used in the chat header. */
export function SnippetShelf() {
  const { snippets } = useSnippets();

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button size="sm" variant="ghost" className="gap-1.5" title="Snippet Shelf">
          <BookmarkIcon className="size-4" />
          <span className="hidden sm:inline">Snippets</span>
          {snippets.length > 0 && (
            <Badge variant="secondary" className="ml-0.5 h-4 min-w-4 px-1 text-[10px]">
              {snippets.length}
            </Badge>
          )}
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="flex w-[400px] flex-col sm:w-[440px]">
        <SnippetShelfContent />
      </SheetContent>
    </Sheet>
  );
}
