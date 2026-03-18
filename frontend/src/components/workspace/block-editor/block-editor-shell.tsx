"use client";

import {
  ArrowUpRightIcon,
  BookOpenTextIcon,
  CopyIcon,
  DownloadIcon,
  FileClockIcon,
  Loader2Icon,
  SaveIcon,
  Wand2Icon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useTransformDocument, useUpdateDocument } from "@/core/documents/hooks";
import type { DocumentRecord, DocumentTransformOperation } from "@/core/documents/types";
import { formatTimeAgo } from "@/core/utils/datetime";

import { BlockEditor, type BlockEditorHandle } from "./block-editor";
import { extractHeadings } from "./markdown-conversion";

const DEFAULT_OPERATION: DocumentTransformOperation = "rewrite";

export function BlockEditorShell({ document }: { document: DocumentRecord }) {
  const updateDocument = useUpdateDocument(document.doc_id);
  const transformDocument = useTransformDocument(document.doc_id);
  const [title, setTitle] = useState(document.title);
  const [markdown, setMarkdown] = useState(document.content_markdown);
  const [editorJson, setEditorJson] = useState<Record<string, unknown> | null>(
    document.editor_json ?? null,
  );
  const [wordCount, setWordCount] = useState(
    document.content_markdown.trim().length > 0
      ? document.content_markdown.trim().split(/\s+/).length
      : 0,
  );
  const [characterCount, setCharacterCount] = useState(document.content_markdown.length);
  const [customInstruction, setCustomInstruction] = useState("");
  const [operation, setOperation] = useState<DocumentTransformOperation>(DEFAULT_OPERATION);
  const [saveState, setSaveState] = useState<"saved" | "dirty" | "saving">("saved");
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const readyRef = useRef(false);
  const editorRef = useRef<BlockEditorHandle | null>(null);

  useEffect(() => {
    setTitle(document.title);
    setMarkdown(document.content_markdown);
    setEditorJson(document.editor_json ?? null);
    setSaveState("saved");
    readyRef.current = false;
  }, [document.doc_id, document.title, document.content_markdown, document.editor_json]);

  const headings = useMemo(() => extractHeadings(markdown), [markdown]);

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
          title: title.trim() || "Untitled document",
          content_markdown: markdown,
          editor_json: editorJson,
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
  }, [editorJson, markdown, title, updateDocument]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const isSave = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s";
      if (!isSave) {
        return;
      }
      event.preventDefault();
      void handleManualSave();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (saveState === "saved") {
        return;
      }
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
        title: title.trim() || "Untitled document",
        content_markdown: markdown,
        editor_json: editorJson,
        status: "active",
      });
      setSaveState("saved");
      toast.success("Document saved");
    } catch (error) {
      setSaveState("dirty");
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleTransform() {
    try {
      const selectionMarkdown = editorRef.current?.getSelectionMarkdown() ?? "";
      const targetMarkdown = selectionMarkdown || markdown;
      const response = await transformDocument.mutateAsync({
        document_markdown: markdown,
        selection_markdown: targetMarkdown,
        operation,
        instruction: operation === "custom" ? customInstruction : undefined,
      });
      if (selectionMarkdown) {
        editorRef.current?.replaceSelectionMarkdown(response.transformed_markdown);
      } else {
        setMarkdown(response.transformed_markdown);
        setEditorJson(null);
      }
      toast.success(`Applied ${operation} with ${response.model_name}`);
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
    anchor.download = `${title.trim() || "document"}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="grid size-full min-h-0 grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="min-h-0 space-y-4">
        <Card className="gap-4 py-4">
          <CardHeader className="px-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <BookOpenTextIcon className="size-4" />
                  Block Editor
                </CardTitle>
                <CardDescription>
                  Refine the document directly, then save or export the final markdown.
                </CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{wordCount} words</Badge>
                <Badge variant="outline">{characterCount} chars</Badge>
                <Badge variant="outline">{document.status}</Badge>
                <Badge variant={saveState === "saved" ? "secondary" : "outline"}>
                  {saveState === "saving" ? "Saving..." : saveState === "dirty" ? "Unsaved changes" : "Saved"}
                </Badge>
                <Button size="sm" variant="outline" onClick={() => void handleCopyMarkdown()}>
                  <CopyIcon className="size-4" />
                  Copy Markdown
                </Button>
                <Button size="sm" variant="outline" onClick={() => handleDownloadMarkdown()}>
                  <DownloadIcon className="size-4" />
                  Download
                </Button>
                <Button size="sm" variant="outline" onClick={() => void handleManualSave()} disabled={updateDocument.isPending}>
                  {updateDocument.isPending ? <Loader2Icon className="size-4 animate-spin" /> : <SaveIcon className="size-4" />}
                  Save
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 px-4">
            <Input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Document title"
            />
            <div className="text-muted-foreground flex items-center justify-between text-xs">
              <span>Autosaves after 1.2s of idle time.</span>
              <span>Shortcut: Cmd/Ctrl+S</span>
            </div>
            <BlockEditor
              ref={editorRef}
              markdown={markdown}
              editorJson={editorJson}
              onChange={({ markdown: nextMarkdown, editorJson: nextJson, wordCount: nextWordCount, characterCount: nextCharCount }) => {
                setMarkdown(nextMarkdown);
                setEditorJson(nextJson);
                setWordCount(nextWordCount);
                setCharacterCount(nextCharCount);
              }}
            />
          </CardContent>
        </Card>
      </div>

      <div className="min-h-0 space-y-4">
        <Card className="gap-4 py-4">
          <CardHeader className="px-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <Wand2Icon className="size-4" />
              AI Refinement
            </CardTitle>
            <CardDescription>
              Apply an AI transform to the current selection when possible, or to the whole draft when nothing is selected.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 px-4">
            <div className="grid grid-cols-2 gap-2">
              {([
                "rewrite",
                "shorten",
                "expand",
                "improve-clarity",
                "executive-summary",
                "bullets",
              ] as DocumentTransformOperation[]).map((value) => (
                <Button
                  key={value}
                  type="button"
                  size="sm"
                  variant={operation === value ? "default" : "outline"}
                  onClick={() => setOperation(value)}
                >
                  {value}
                </Button>
              ))}
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
            <Button
              type="button"
              className="w-full"
              onClick={() => void handleTransform()}
              disabled={transformDocument.isPending || (operation === "custom" && customInstruction.trim().length === 0)}
            >
              {transformDocument.isPending ? (
                <Loader2Icon className="size-4 animate-spin" />
              ) : (
                <Wand2Icon className="size-4" />
              )}
              Apply transform
            </Button>
            <div className="text-muted-foreground text-xs">
              Tip: select a paragraph or block first to target only that section.
            </div>
          </CardContent>
        </Card>

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

        <Card className="gap-4 py-4">
          <CardHeader className="px-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <FileClockIcon className="size-4" />
              Provenance
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 px-4 text-sm">
            <div>Updated {formatTimeAgo(document.updated_at)}</div>
            {document.source_run_id && <div>Doc-edit run: {document.source_run_id}</div>}
            {document.source_version_id && <div>Version: {document.source_version_id}</div>}
            {document.source_filepath && <div className="break-all">Artifact: {document.source_filepath}</div>}
            {document.source_run_id && (
              <Link
                className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                href={`/workspace/doc-edits/${document.source_run_id}`}
              >
                Open source run
                <ArrowUpRightIcon className="size-4" />
              </Link>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
