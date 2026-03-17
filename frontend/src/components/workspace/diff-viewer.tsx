"use client";

import { MergeView } from "@codemirror/merge";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

export function DiffViewer({
  original,
  modified,
  className,
}: {
  original: string;
  modified: string;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<MergeView | null>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    if (!containerRef.current) return;

    // Clean up previous instance
    if (viewRef.current) {
      viewRef.current.destroy();
      viewRef.current = null;
    }

    const isDark = resolvedTheme === "dark";

    const baseTheme = EditorView.theme({
      "&": {
        fontSize: "0.875rem",
        lineHeight: "1.5rem",
        background: "transparent",
      },
      ".cm-mergeView": {
        height: "100%",
      },
      ".cm-mergeViewEditors": {
        height: "100%",
      },
      ".cm-changedLine": {
        background: isDark ? "rgba(255, 180, 50, 0.08)" : "rgba(255, 180, 50, 0.12)",
      },
      ".cm-changedText": {
        background: isDark ? "rgba(255, 180, 50, 0.2)" : "rgba(255, 180, 50, 0.25)",
      },
      ".cm-deletedChunk": {
        background: isDark ? "rgba(248, 81, 73, 0.12)" : "rgba(248, 81, 73, 0.15)",
      },
      ".cm-insertedLine": {
        background: isDark ? "rgba(63, 185, 80, 0.1)" : "rgba(63, 185, 80, 0.15)",
      },
      ".cm-deletedLine": {
        background: isDark ? "rgba(248, 81, 73, 0.1)" : "rgba(248, 81, 73, 0.12)",
      },
      ".cm-gutters": {
        background: "transparent",
        border: "none",
      },
      ".cm-content": {
        fontFamily: "inherit",
      },
    });

    const sharedExtensions = [
      EditorView.editable.of(false),
      EditorState.readOnly.of(true),
      EditorView.lineWrapping,
      baseTheme,
    ];

    const view = new MergeView({
      parent: containerRef.current,
      a: {
        doc: original,
        extensions: sharedExtensions,
      },
      b: {
        doc: modified,
        extensions: sharedExtensions,
      },
      collapseUnchanged: { margin: 3, minSize: 4 },
      gutter: true,
    });

    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
  }, [original, modified, resolvedTheme]);

  return (
    <div
      ref={containerRef}
      className={cn(
        "overflow-auto rounded-lg border [&_.cm-mergeView]:min-h-0",
        className,
      )}
    />
  );
}
