"use client";

import {
  ArrowUpRightIcon,
  BookOpenTextIcon,
  BookTextIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CopyIcon,
  DownloadIcon,
  FileClockIcon,
  FilePenLineIcon,
  HistoryIcon,
  Loader2Icon,
  PlusIcon,
  SaveIcon,
  SearchIcon,
  Trash2Icon,
  Wand2Icon,
} from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { getBackendBaseURL } from "@/core/config";
import { useDocEditRuns } from "@/core/doc-editing/hooks";
import type { DocEditRun, DocEditVersion } from "@/core/doc-editing/types";
import {
  useCreateDocumentQuickAction,
  useCreateDocumentSnapshot,
  useDeleteDocumentQuickAction,
  useDocumentQuickActions,
  useDocumentSnapshots,
  useRestoreDocumentSnapshot,
  useTransformDocument,
  useUpdateDocument,
} from "@/core/documents/hooks";
import type {
  DocumentQuickAction,
  DocumentRecord,
  DocumentSnapshot,
  DocumentTransformOperation,
} from "@/core/documents/types";
import { formatTimeAgo } from "@/core/utils/datetime";

import { BlockEditor, type BlockEditorHandle } from "./block-editor";
import { ClipsBoard } from "./clips-board";
import { extractHeadings } from "./markdown-conversion";
import { RevisionLabPanel } from "./revision-lab-panel";

const DEFAULT_OPERATION: DocumentTransformOperation = "rewrite";
const DiffViewer = dynamic(
  () => import("@/components/workspace/diff-viewer").then((m) => m.DiffViewer),
  { ssr: false, loading: () => <div className="text-muted-foreground text-sm">Loading diff…</div> },
);

// ─── History panel ────────────────────────────────────────────────────────────

function VersionCard({
  version,
  onInsert,
}: {
  version: DocEditVersion;
  onInsert: (text: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const preview = version.output?.slice(0, 180);
  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="font-medium">{version.skill_name}</span>
          {version.model_name && (
            <span className="text-muted-foreground ml-1">· {version.model_name}</span>
          )}
          {version.score > 0 && (
            <Badge variant="secondary" className="ml-1 h-4 px-1 text-[10px]">
              {(version.score * 100).toFixed(0)}
            </Badge>
          )}
        </div>
        <button
          type="button"
          className="text-muted-foreground shrink-0 hover:text-foreground"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? <ChevronDownIcon className="size-3.5" /> : <ChevronRightIcon className="size-3.5" />}
        </button>
      </div>
      {expanded && version.output && (
        <p className="mt-1 text-muted-foreground whitespace-pre-wrap">{preview}{(version.output.length > 180) ? "…" : ""}</p>
      )}
      {version.output && (
        <Button
          size="sm"
          variant="ghost"
          className="mt-1 h-6 px-2 text-xs"
          onClick={() => onInsert(version.output!)}
        >
          Insert into draft
        </Button>
      )}
    </div>
  );
}


function HistoryPanel({ onInsert }: { onInsert: (text: string) => void }) {
  const { data, isLoading } = useDocEditRuns();
  if (isLoading) {
    return <div className="text-muted-foreground py-2 text-xs">Loading revision history...</div>;
  }
  if (!data?.runs?.length) {
    return (
      <div className="text-muted-foreground text-xs">
        No revision sessions yet. Use <em>Revision Lab</em> to generate versions.
      </div>
    );
  }
  // We need full run data to show versions — runs list only has summaries.
  // Render stubs for summary rows, users can open Revision Lab for details.
  const stubs: DocEditRun[] = data.runs.map((r) => ({
    run_id: r.run_id,
    title: r.title,
    run_dir: "",
    status: r.status,
    final_path: r.final_path ?? null,
    selected_skill: r.selected_skill ?? null,
    versions: [],
    token_count: r.token_count ?? 0,
  }));
  return (
    <div className="space-y-2">
      {stubs.map((run) => (
        <HistoryRunStub key={run.run_id} run={run} onInsert={onInsert} />
      ))}
    </div>
  );
}

function HistoryRunStub({
  run,
  onInsert,
}: {
  run: DocEditRun;
  onInsert: (text: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  // Lazy-load full run data only when expanded
  const [fullRun, setFullRun] = useState<DocEditRun | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleExpand() {
    const next = !expanded;
    setExpanded(next);
    if (next && !fullRun) {
      setLoading(true);
      try {
        const response = await fetch(`${getBackendBaseURL()}/api/doc-edit/${run.run_id}`);
        if (response.ok) {
          const data = (await response.json()) as DocEditRun;
          setFullRun(data);
        }
      } finally {
        setLoading(false);
      }
    }
  }

  const displayRun = fullRun ?? run;
  return (
    <div className="rounded-xl border text-xs">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-muted/40 transition-colors"
        onClick={() => void handleExpand()}
      >
        <div className="min-w-0">
          <span className="font-medium">{run.title ?? run.run_id.slice(0, 16)}</span>
          {run.selected_skill && (
            <Badge variant="secondary" className="ml-1 h-4 px-1 text-[10px]">{run.selected_skill}</Badge>
          )}
        </div>
        {expanded ? <ChevronDownIcon className="size-3.5 shrink-0" /> : <ChevronRightIcon className="size-3.5 shrink-0" />}
      </button>
      {expanded && (
        <div className="border-t px-3 pb-3 pt-2 space-y-2">
          {loading && <div className="text-muted-foreground">Loading run variants...</div>}
          {!loading && displayRun.versions.length === 0 && (
            <div className="text-muted-foreground">No variants available for this run.</div>
          )}
          {displayRun.versions.map((v, i) => (
            <VersionCard key={v.version_id ?? i} version={v} onInsert={onInsert} />
          ))}
          <Link
            href={`/workspace/doc-edits/${run.run_id}`}
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            Open full run in Revision Lab
            <ArrowUpRightIcon className="size-3" />
          </Link>
        </div>
      )}
    </div>
  );
}

// ─── Shell ────────────────────────────────────────────────────────────────────

export function BlockEditorShell({
  document,
  editorHandleRef,
}: {
  document: DocumentRecord;
  editorHandleRef?: React.MutableRefObject<BlockEditorHandle | null>;
}) {
  const updateDocument = useUpdateDocument(document.doc_id);
  const transformDocument = useTransformDocument(document.doc_id);
  const { data: quickActionsData } = useDocumentQuickActions();
  const { data: snapshotsData } = useDocumentSnapshots(document.doc_id);
  const createQuickAction = useCreateDocumentQuickAction();
  const deleteQuickAction = useDeleteDocumentQuickAction();
  const createSnapshot = useCreateDocumentSnapshot(document.doc_id);
  const restoreSnapshot = useRestoreDocumentSnapshot(document.doc_id);
  const [title, setTitle] = useState(document.title);
  const [markdown, setMarkdown] = useState(document.content_markdown);
  const [editorJson, setEditorJson] = useState<Record<string, unknown> | null>(
    document.editor_json ?? null,
  );
  const [writingMemory, setWritingMemory] = useState(document.writing_memory ?? "");
  const [wordCount, setWordCount] = useState(
    document.content_markdown.trim().length > 0
      ? document.content_markdown.trim().split(/\s+/).length
      : 0,
  );
  const [characterCount, setCharacterCount] = useState(document.content_markdown.length);
  const [customInstruction, setCustomInstruction] = useState("");
  const [operation, setOperation] = useState<DocumentTransformOperation>(DEFAULT_OPERATION);
  const [saveState, setSaveState] = useState<"saved" | "dirty" | "saving">("saved");
  const [revisionLab, setRevisionLab] = useState<{ content: string; isSelection: boolean } | null>(null);
  const [quickActionName, setQuickActionName] = useState("");
  const [quickActionInstruction, setQuickActionInstruction] = useState("");
  const [snapshotLabel, setSnapshotLabel] = useState("");
  const [snapshotNote, setSnapshotNote] = useState("");
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const readyRef = useRef(false);
  const editorRef = useRef<BlockEditorHandle | null>(null);

  // Sync external handle ref on every render so callers can call insertMarkdown
  if (editorHandleRef !== undefined) {
    editorHandleRef.current = editorRef.current;
  }

  useEffect(() => {
    setTitle(document.title);
    setMarkdown(document.content_markdown);
    setEditorJson(document.editor_json ?? null);
    setWritingMemory(document.writing_memory ?? "");
    setSaveState("saved");
    readyRef.current = false;
  }, [document.doc_id, document.title, document.content_markdown, document.editor_json, document.writing_memory]);

  const headings = useMemo(() => extractHeadings(markdown), [markdown]);
  const quickActions = useMemo(() => quickActionsData?.actions ?? [], [quickActionsData?.actions]);
  const snapshots = useMemo(() => snapshotsData?.snapshots ?? [], [snapshotsData?.snapshots]);
  const selectedSnapshot = useMemo(
    () => snapshots.find((snapshot) => snapshot.snapshot_id === selectedSnapshotId) ?? snapshots[0] ?? null,
    [selectedSnapshotId, snapshots],
  );
  const selectionPreview = editorRef.current?.getSelectionMarkdown().trim() ?? "";

  useEffect(() => {
    if (!readyRef.current) {
      readyRef.current = true;
      return;
    }
    setSaveState("dirty");
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    saveTimeoutRef.current = setTimeout(() => {
      setSaveState("saving");
      updateDocument
        .mutateAsync({
          title: title.trim() || "Untitled piece",
          content_markdown: markdown,
          editor_json: editorJson,
          writing_memory: writingMemory,
          status: "active",
        })
        .then(() => setSaveState("saved"))
        .catch((error) => {
          setSaveState("dirty");
          toast.error(error instanceof Error ? error.message : String(error));
        });
    }, 1200);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [editorJson, markdown, title, updateDocument, writingMemory]);

  useEffect(() => {
    if (!selectedSnapshotId && snapshots[0]?.snapshot_id) {
      setSelectedSnapshotId(snapshots[0].snapshot_id);
    }
  }, [selectedSnapshotId, snapshots]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const isSave = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s";
      if (!isSave) return;
      event.preventDefault();
      void handleManualSave();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (saveState === "saved") return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [saveState]);

  async function handleManualSave() {
    try {
      setSaveState("saving");
      await updateDocument.mutateAsync({
        title: title.trim() || "Untitled piece",
        content_markdown: markdown,
        editor_json: editorJson,
        writing_memory: writingMemory,
        status: "active",
      });
      setSaveState("saved");
      toast.success("Piece saved");
    } catch (error) {
      setSaveState("dirty");
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleTransform(overrides?: {
    operation?: DocumentTransformOperation;
    instruction?: string;
  }) {
    try {
      const selectionMarkdown = editorRef.current?.getSelectionMarkdown() ?? "";
      const targetMarkdown = selectionMarkdown || markdown;
      const nextOperation = overrides?.operation ?? operation;
      const nextInstruction = overrides?.instruction ?? (nextOperation === "custom" ? customInstruction : undefined);
      const response = await transformDocument.mutateAsync({
        document_markdown: markdown,
        selection_markdown: targetMarkdown,
        operation: nextOperation,
        instruction: nextInstruction,
        writing_memory: writingMemory,
      });
      if (selectionMarkdown) {
        editorRef.current?.replaceSelectionMarkdown(response.transformed_markdown);
      } else {
        setMarkdown(response.transformed_markdown);
        setEditorJson(null);
      }
      toast.success(`Applied ${nextOperation} with ${response.model_name}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleCopyMarkdown() {
    try {
      await navigator.clipboard.writeText(markdown);
      toast.success("Markdown copied to clipboard");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to copy markdown");
    }
  }

  function handleDownloadMarkdown() {
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = `${title.trim() || "untitled-piece"}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function handleOpenRevisionLab(scope: "selection" | "document") {
    const selectedMarkdown = editorRef.current?.getSelectionMarkdown().trim() ?? "";
    if (scope === "selection" && selectedMarkdown.length === 0) {
      toast.error("Select a block or paragraph first");
      return;
    }
    setRevisionLab({
      content: scope === "selection" ? selectedMarkdown : markdown,
      isSelection: scope === "selection",
    });
  }

  function handleInsertAtCursor(text: string) {
    editorRef.current?.insertMarkdown(text);
  }

  async function handleSaveQuickAction() {
    if (!quickActionName.trim() || !quickActionInstruction.trim()) {
      toast.error("Name the desk card and add an instruction first");
      return;
    }
    try {
      await createQuickAction.mutateAsync({
        name: quickActionName.trim(),
        instruction: quickActionInstruction.trim(),
      });
      setQuickActionName("");
      setQuickActionInstruction("");
      toast.success("Desk card saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleApplyQuickAction(action: DocumentQuickAction) {
    setOperation("custom");
    setCustomInstruction(action.instruction);
    await handleTransform({ operation: "custom", instruction: action.instruction });
  }

  async function handleDeleteQuickAction(actionId: string) {
    try {
      await deleteQuickAction.mutateAsync(actionId);
      toast.success("Desk card removed");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleCreateSnapshot() {
    try {
      const snapshot = await createSnapshot.mutateAsync({
        label: snapshotLabel.trim() || undefined,
        note: snapshotNote.trim() || undefined,
        source: "manual",
      });
      setSnapshotLabel("");
      setSnapshotNote("");
      setSelectedSnapshotId(snapshot.snapshot_id);
      toast.success("Snapshot saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleRestoreSnapshot(snapshot: DocumentSnapshot) {
    try {
      const restored = await restoreSnapshot.mutateAsync(snapshot.snapshot_id);
      setTitle(restored.title);
      setMarkdown(restored.content_markdown);
      setEditorJson(restored.editor_json ?? null);
      setWritingMemory(restored.writing_memory ?? "");
      setSaveState("saved");
      toast.success(`Restored snapshot: ${snapshot.label}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <div className={`grid size-full min-h-0 grid-cols-1 gap-6 ${revisionLab ? "xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]" : "xl:grid-cols-[minmax(0,1fr)_22rem]"}`}>
      {/* Editor column */}
      <div className="min-h-0 space-y-4">
        <Card className="gap-4 border-border/70 bg-background/92 py-4 shadow-sm">
          <CardHeader className="px-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-2">
                <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
                  Writing Desk
                </div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BookOpenTextIcon className="size-4" />
                  Composer
                </CardTitle>
                <CardDescription>
                  Shape the draft directly, then save it, export it, or send a passage into Revision Lab.
                </CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{wordCount} words</Badge>
                <Badge variant="outline">{characterCount} chars</Badge>
                <Badge variant="outline" className="bg-muted/30">{document.status}</Badge>
                <Badge variant={saveState === "saved" ? "secondary" : "outline"}>
                  {saveState === "saving" ? "Saving..." : saveState === "dirty" ? "Not saved" : "Saved"}
                </Badge>
                <Button size="sm" variant="outline" onClick={() => void handleCopyMarkdown()}>
                  <CopyIcon className="size-4" />
                  Copy
                </Button>
                <Button size="sm" variant="outline" onClick={() => handleDownloadMarkdown()}>
                  <DownloadIcon className="size-4" />
                  Download
                </Button>
                <Button size="sm" variant="outline" onClick={() => handleOpenRevisionLab("document")}>
                  <FilePenLineIcon className="size-4" />
                  Send to Revision Lab
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void handleManualSave()}
                  disabled={updateDocument.isPending}
                >
                  {updateDocument.isPending ? (
                    <Loader2Icon className="size-4 animate-spin" />
                  ) : (
                    <SaveIcon className="size-4" />
                  )}
                  Save
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 px-4">
            <Input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Piece title"
            />
            <div className="text-muted-foreground flex items-center justify-between text-xs">
              <span>Autosaves after 1.2s of idle time so the desk stays current.</span>
              <span>Shortcut: Cmd/Ctrl+S</span>
            </div>
            <BlockEditor
              ref={editorRef}
              markdown={markdown}
              editorJson={editorJson}
              onChange={({
                markdown: nextMarkdown,
                editorJson: nextJson,
                wordCount: nextWordCount,
                characterCount: nextCharCount,
              }) => {
                setMarkdown(nextMarkdown);
                setEditorJson(nextJson);
                setWordCount(nextWordCount);
                setCharacterCount(nextCharCount);
              }}
            />
          </CardContent>
        </Card>
      </div>

      {/* Sidebar / Revision Lab */}
      <div className="min-h-0">
        {revisionLab ? (
          <RevisionLabPanel
            originalContent={revisionLab.content}
            isSelection={revisionLab.isSelection}
            onAccept={(acceptedMarkdown) => {
              if (revisionLab.isSelection) {
                editorRef.current?.replaceSelectionMarkdown(acceptedMarkdown);
              } else {
                setMarkdown(acceptedMarkdown);
                setEditorJson(null);
              }
            }}
            onClose={() => setRevisionLab(null)}
          />
        ) : (
        <Tabs defaultValue="refine" className="flex h-full flex-col">
          <TabsList className="grid w-full grid-cols-5 shrink-0">
            <TabsTrigger value="refine" title="Refine & Compare">
              <Wand2Icon className="size-3.5" />
            </TabsTrigger>
            <TabsTrigger value="sources" title="Sources">
              <SearchIcon className="size-3.5" />
            </TabsTrigger>
            <TabsTrigger value="history" title="Version History">
              <HistoryIcon className="size-3.5" />
            </TabsTrigger>
            <TabsTrigger value="snapshots" title="Snapshots">
              <FileClockIcon className="size-3.5" />
            </TabsTrigger>
            <TabsTrigger value="outline" title="Outline">
              <BookTextIcon className="size-3.5" />
            </TabsTrigger>
          </TabsList>

          {/* ── Refine ── */}
          <TabsContent value="refine" className="mt-3 flex-1 overflow-y-auto space-y-4">
            <Card className="gap-4 border-border/70 bg-background/90 py-4 shadow-sm">
              <CardHeader className="px-4">
                <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
                  Revision Moves
                </div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Wand2Icon className="size-4" />
                  Refine & Compare
                </CardTitle>
                <CardDescription>
                  Work like a composer at a messy desk: keep favorite moves on hand, jot the voice rules you want the AI to respect, and send only the parts that need revision into the lab.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 px-4">
                <div className="grid grid-cols-2 gap-2">
                  {(["rewrite", "shorten", "expand", "improve-clarity", "executive-summary", "bullets"] as DocumentTransformOperation[]).map(
                    (value) => (
                      <Button
                        key={value}
                        type="button"
                        size="sm"
                        variant={operation === value ? "default" : "outline"}
                        onClick={() => setOperation(value)}
                      >
                        {value}
                      </Button>
                    ),
                  )}
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant={operation === "custom" ? "default" : "outline"}
                  onClick={() => setOperation("custom")}
                  className="w-full"
                >
                  Custom instruction
                </Button>
                {operation === "custom" && (
                  <Textarea
                    value={customInstruction}
                    onChange={(event) => setCustomInstruction(event.target.value)}
                    className="min-h-28"
                    placeholder="Tell the AI exactly how to transform the current draft..."
                  />
                )}
                <div className="rounded-2xl border border-border/70 bg-[linear-gradient(135deg,rgba(217,119,6,0.08),transparent_55%),linear-gradient(180deg,rgba(255,255,255,0.02),rgba(255,255,255,0))] p-3">
                  <div className="text-sm font-medium">Writing Memory</div>
                  <div className="text-muted-foreground mt-1 text-xs">
                    Pinned style cues, recurring constraints, and reminders for this piece. They are applied to every transform.
                  </div>
                  <Textarea
                    value={writingMemory}
                    onChange={(event) => setWritingMemory(event.target.value)}
                    className="mt-3 min-h-28"
                    placeholder="Examples: Keep the tone clipped and precise. Let fragments stay fragmentary. Prefer image clusters over explanation."
                  />
                </div>
                <Button
                  type="button"
                  className="w-full"
                  onClick={() => void handleTransform()}
                  disabled={
                    transformDocument.isPending ||
                    (operation === "custom" && customInstruction.trim().length === 0)
                  }
                >
                  {transformDocument.isPending ? (
                    <Loader2Icon className="size-4 animate-spin" />
                  ) : (
                    <Wand2Icon className="size-4" />
                  )}
                  Apply transform
                </Button>
                <div className="text-muted-foreground text-xs">
                  {selectionPreview.length > 0
                    ? "A selection is active. Transforms and Revision Lab can target just this passage."
                    : "Select a paragraph or block first to target only that section."}
                </div>
                <div className="grid grid-cols-1 gap-2 pt-1">
                  <Button type="button" variant="outline" onClick={() => handleOpenRevisionLab("selection")}>
                    <FilePenLineIcon className="size-4" />
                    Compare selection in Revision Lab
                  </Button>
                  <Button type="button" variant="outline" onClick={() => handleOpenRevisionLab("document")}>
                    <FilePenLineIcon className="size-4" />
                    Compare full draft in Revision Lab
                  </Button>
                </div>
                <div className="rounded-2xl border border-border/70 bg-[linear-gradient(135deg,rgba(20,83,45,0.08),transparent_60%),linear-gradient(180deg,rgba(255,255,255,0.02),rgba(255,255,255,0))] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-medium">Desk Cards</div>
                      <div className="text-muted-foreground mt-1 text-xs">
                        Saved quick actions for recurring edits you want nearby while drafting.
                      </div>
                    </div>
                    <Badge variant="outline">{quickActions.length}</Badge>
                  </div>
                  <div className="mt-3 space-y-2">
                    {quickActions.length === 0 ? (
                      <div className="text-muted-foreground rounded-lg border border-dashed px-3 py-2 text-xs">
                        No saved quick actions yet.
                      </div>
                    ) : (
                      quickActions.map((action) => (
                        <div key={action.action_id} className="rounded-lg border bg-background/70 px-3 py-2">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <div className="text-sm font-medium">{action.name}</div>
                              <div className="text-muted-foreground mt-1 text-xs whitespace-pre-wrap">
                                {action.instruction}
                              </div>
                            </div>
                            <Button
                              type="button"
                              size="icon-sm"
                              variant="ghost"
                              onClick={() => void handleDeleteQuickAction(action.action_id)}
                              disabled={deleteQuickAction.isPending}
                            >
                              <Trash2Icon className="size-3.5" />
                            </Button>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="mt-2"
                            onClick={() => void handleApplyQuickAction(action)}
                            disabled={transformDocument.isPending}
                          >
                            <Wand2Icon className="size-4" />
                            Apply
                          </Button>
                        </div>
                      ))
                    )}
                  </div>
                  <div className="mt-3 grid grid-cols-1 gap-2">
                    <Input
                      value={quickActionName}
                      onChange={(event) => setQuickActionName(event.target.value)}
                      placeholder="Desk card name"
                    />
                    <Textarea
                      value={quickActionInstruction}
                      onChange={(event) => setQuickActionInstruction(event.target.value)}
                      className="min-h-24"
                      placeholder="Instruction to save for one-click transforms..."
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void handleSaveQuickAction()}
                      disabled={createQuickAction.isPending}
                    >
                      {createQuickAction.isPending ? (
                        <Loader2Icon className="size-4 animate-spin" />
                      ) : (
                        <PlusIcon className="size-4" />
                      )}
                      Save quick action
                    </Button>
                  </div>
                </div>
                <div className="rounded-xl border border-dashed border-border/70 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                  Quick transforms are best for surgical edits. Desk cards hold favorite moves. Revision Lab is still the right place for side-by-side strategy comparison.
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Sources ── */}
          <TabsContent value="sources" className="mt-3 flex-1 overflow-y-auto">
            <ClipsBoard docId={document.doc_id} onInsert={handleInsertAtCursor} />
          </TabsContent>

          {/* ── History ── */}
          <TabsContent value="history" className="mt-3 flex-1 overflow-y-auto space-y-3">
            <Card className="gap-4 border-border/70 bg-background/90 py-4 shadow-sm">
              <CardHeader className="px-4">
                <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
                  Revision Archive
                </div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <HistoryIcon className="size-4" />
                  Revision History
                </CardTitle>
                <CardDescription>
                  Pick a version from any prior run and insert it at your cursor.
                </CardDescription>
              </CardHeader>
              <CardContent className="px-4">
                <HistoryPanel onInsert={handleInsertAtCursor} />
              </CardContent>
            </Card>

            {document.source_run_id && (
              <Card className="gap-4 border-border/70 bg-background/90 py-4 shadow-sm">
                <CardHeader className="px-4">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <FileClockIcon className="size-4" />
                    Provenance
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 px-4 text-sm">
                  <div>Updated {formatTimeAgo(document.updated_at)}</div>
                  {document.source_run_id && <div>Run: {document.source_run_id}</div>}
                  {document.source_version_id && <div>Version: {document.source_version_id}</div>}
                  {document.source_filepath && (
                    <div className="break-all">Artifact: {document.source_filepath}</div>
                  )}
                  <Link
                    className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                    href={`/workspace/doc-edits/${document.source_run_id}`}
                  >
                    Open source revision
                    <ArrowUpRightIcon className="size-4" />
                  </Link>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ── Snapshots ── */}
          <TabsContent value="snapshots" className="mt-3 flex-1 overflow-y-auto space-y-3">
            <Card className="gap-4 border-border/70 bg-background/90 py-4 shadow-sm">
              <CardHeader className="px-4">
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileClockIcon className="size-4" />
                  Draft Snapshots
                </CardTitle>
                <CardDescription>
                  Save states of the draft as you move pieces around the desk, then compare or restore them later.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 px-4">
                <Input
                  value={snapshotLabel}
                  onChange={(event) => setSnapshotLabel(event.target.value)}
                  placeholder="Snapshot label"
                />
                <Textarea
                  value={snapshotNote}
                  onChange={(event) => setSnapshotNote(event.target.value)}
                  className="min-h-24"
                  placeholder="Optional note about what changed or why this state matters..."
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleCreateSnapshot()}
                  disabled={createSnapshot.isPending}
                >
                  {createSnapshot.isPending ? (
                    <Loader2Icon className="size-4 animate-spin" />
                  ) : (
                    <PlusIcon className="size-4" />
                  )}
                  Save draft snapshot
                </Button>
              </CardContent>
            </Card>

            <Card className="gap-4 border-border/70 bg-background/90 py-4 shadow-sm">
              <CardHeader className="px-4">
                <CardTitle className="text-base">Snapshot Stack</CardTitle>
                <CardDescription>
                  Pick a snapshot to compare against the current draft, then restore if you want to roll back.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 px-4">
                {snapshots.length === 0 ? (
                  <div className="text-muted-foreground rounded-lg border border-dashed px-3 py-4 text-sm">
                    No snapshots yet. Save one before a major rewrite, merge, or structural change.
                  </div>
                ) : (
                  snapshots.map((snapshot) => (
                    <button
                      key={snapshot.snapshot_id}
                      type="button"
                      className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${
                        selectedSnapshot?.snapshot_id === snapshot.snapshot_id
                          ? "border-primary bg-primary/5"
                          : "hover:bg-muted/30"
                      }`}
                      onClick={() => setSelectedSnapshotId(snapshot.snapshot_id)}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-sm font-medium">{snapshot.label}</div>
                          <div className="text-muted-foreground mt-1 text-xs">
                            {formatTimeAgo(snapshot.created_at)} · {snapshot.source}
                          </div>
                        </div>
                        <Badge variant="outline">{snapshot.title}</Badge>
                      </div>
                      {snapshot.note ? (
                        <div className="text-muted-foreground mt-2 text-xs whitespace-pre-wrap">
                          {snapshot.note}
                        </div>
                      ) : null}
                    </button>
                  ))
                )}
              </CardContent>
            </Card>

            {selectedSnapshot ? (
              <Card className="gap-4 border-border/70 bg-background/90 py-4 shadow-sm">
                <CardHeader className="px-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <CardTitle className="text-base">Current Draft vs Snapshot</CardTitle>
                      <CardDescription>{selectedSnapshot.label}</CardDescription>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void handleRestoreSnapshot(selectedSnapshot)}
                      disabled={restoreSnapshot.isPending}
                    >
                      {restoreSnapshot.isPending ? (
                        <Loader2Icon className="size-4 animate-spin" />
                      ) : (
                        <HistoryIcon className="size-4" />
                      )}
                      Restore into Composer
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="px-4">
                  <DiffViewer original={selectedSnapshot.content_markdown} modified={markdown} className="h-[28rem]" />
                </CardContent>
              </Card>
            ) : null}
          </TabsContent>

          {/* ── Outline ── */}
          <TabsContent value="outline" className="mt-3 flex-1 overflow-y-auto">
            <Card className="gap-4 py-4">
              <CardHeader className="px-4">
                <CardTitle className="text-base">Outline</CardTitle>
                <CardDescription>Navigate the structure of the current draft.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 px-4">
                {headings.length === 0 ? (
                  <div className="text-muted-foreground text-sm">Add headings to build an outline.</div>
                ) : (
                  headings.map((heading, index) => (
                    <div
                      key={`${heading.anchor}-${index}`}
                      className="text-sm"
                      style={{ paddingLeft: `${(heading.level - 1) * 12}px` }}
                    >
                      {heading.text}
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
        )}
      </div>
    </div>
  );
}
