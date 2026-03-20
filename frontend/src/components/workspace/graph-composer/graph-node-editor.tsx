"use client";

import { LexicalComposer } from "@lexical/react/LexicalComposer";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import { ContentEditable } from "@lexical/react/LexicalContentEditable";
import { LexicalErrorBoundary } from "@lexical/react/LexicalErrorBoundary";
import { HistoryPlugin } from "@lexical/react/LexicalHistoryPlugin";
import { OnChangePlugin } from "@lexical/react/LexicalOnChangePlugin";
import { PlainTextPlugin } from "@lexical/react/LexicalPlainTextPlugin";
import { $createParagraphNode, $createTextNode, $getRoot, type EditorState } from "lexical";
import { useEffect } from "react";

import { cn } from "@/lib/utils";

function seedEditorState(text: string) {
  return () => {
    const root = $getRoot();
    root.clear();
    const paragraph = $createParagraphNode();
    const lines = text.split("\n");
    lines.forEach((line, index) => {
      paragraph.append($createTextNode(line));
      if (index < lines.length - 1) {
        paragraph.append($createTextNode("\n"));
      }
    });
    root.append(paragraph);
  };
}

function readPlainText(editorState: EditorState): string {
  let plainText = "";
  editorState.read(() => {
    plainText = $getRoot().getTextContent();
  });
  return plainText;
}

function SyncTextPlugin({ value }: { value: string }) {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    const currentValue = editor.getEditorState().read(() => $getRoot().getTextContent());
    if (currentValue === value) {
      return;
    }
    editor.update(() => {
      const root = $getRoot();
      root.clear();
      const paragraph = $createParagraphNode();
      const lines = value.split("\n");
      lines.forEach((line, index) => {
        paragraph.append($createTextNode(line));
        if (index < lines.length - 1) {
          paragraph.append($createTextNode("\n"));
        }
      });
      root.append(paragraph);
    });
  }, [editor, value]);

  return null;
}

export function GraphNodeEditor({
  value,
  placeholder,
  className,
  onChange,
}: {
  value: string;
  placeholder: string;
  className?: string;
  onChange: (value: string) => void;
}) {
  const initialConfig = {
    namespace: `graph-node-editor-${placeholder}`,
    theme: {
      paragraph: "m-0",
    },
    onError(error: Error) {
      throw error;
    },
    editorState: seedEditorState(value),
  };

  return (
    <LexicalComposer initialConfig={initialConfig}>
      <div className={cn("rounded-xl border border-border/60 bg-background/85 px-3 py-2", className)}>
        <PlainTextPlugin
          contentEditable={
            <ContentEditable className="min-h-[5.5rem] resize-none text-sm leading-6 focus:outline-none" />
          }
          placeholder={<div className="pointer-events-none text-sm text-muted-foreground">{placeholder}</div>}
          ErrorBoundary={LexicalErrorBoundary}
        />
        <HistoryPlugin />
        <SyncTextPlugin value={value} />
        <OnChangePlugin
          onChange={(editorState) => {
            onChange(readPlainText(editorState));
          }}
        />
      </div>
    </LexicalComposer>
  );
}
