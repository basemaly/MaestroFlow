"use client";

import CodeBlockLowlight from "@tiptap/extension-code-block-lowlight";
import Placeholder from "@tiptap/extension-placeholder";
import { Table } from "@tiptap/extension-table";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import TableRow from "@tiptap/extension-table-row";
import TaskItem from "@tiptap/extension-task-item";
import TaskList from "@tiptap/extension-task-list";
import Underline from "@tiptap/extension-underline";
import { type Editor, EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { common, createLowlight } from "lowlight";
import {
  BoldIcon,
  CheckSquareIcon,
  Code2Icon,
  Heading1Icon,
  Heading2Icon,
  ItalicIcon,
  ListIcon,
  ListOrderedIcon,
  MinusIcon,
  QuoteIcon,
  StrikethroughIcon,
  Table2Icon,
  UnderlineIcon,
} from "lucide-react";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import GlobalDragHandle from "tiptap-extension-global-drag-handle";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { htmlToMarkdown, markdownToHtml } from "./markdown-conversion";

const lowlight = createLowlight(common);

export interface BlockEditorHandle {
  getSelectionMarkdown: () => string;
  replaceSelectionMarkdown: (markdown: string) => void;
  insertMarkdown: (markdown: string) => void;
}

function ToolbarButton({
  active,
  onClick,
  title,
  icon: Icon,
}: {
  active?: boolean;
  onClick: () => void;
  title: string;
  icon: React.ElementType;
}) {
  return (
    <Button
      type="button"
      size="icon-sm"
      variant={active ? "default" : "outline"}
      className="rounded-full"
      title={title}
      onClick={onClick}
    >
      <Icon className="size-4" />
    </Button>
  );
}

// ─── Inline format bar (appears above selection) ─────────────────────────────

function InlineFormatBar({ editor }: { editor: Editor }) {
  const barRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => {
    const update = () => {
      const { from, to, empty } = editor.state.selection;
      if (empty) { setPos(null); return; }
      const start = editor.view.coordsAtPos(from);
      const end = editor.view.coordsAtPos(to);
      const editorDom = editor.view.dom;
      const rect = editorDom.getBoundingClientRect();
      const midX = (start.left + end.left) / 2 - rect.left;
      setPos({ top: start.top - rect.top - 44, left: midX });
    };
    editor.on("selectionUpdate", update);
    editor.on("blur", () => setPos(null));
    return () => { editor.off("selectionUpdate", update); editor.off("blur", () => setPos(null)); };
  }, [editor]);

  if (!pos) return null;

  return (
    <div
      ref={barRef}
      className="pointer-events-auto absolute z-50 flex items-center gap-0.5 rounded-xl border border-border/70 bg-background/95 px-1.5 py-1 shadow-lg backdrop-blur-sm"
      style={{ top: pos.top, left: pos.left, transform: "translateX(-50%)" }}
      onMouseDown={(e) => e.preventDefault()}
    >
      {(
        [
          { action: "toggleBold", mark: "bold", Icon: BoldIcon, title: "Bold" },
          { action: "toggleItalic", mark: "italic", Icon: ItalicIcon, title: "Italic" },
          { action: "toggleUnderline", mark: "underline", Icon: UnderlineIcon, title: "Underline" },
          { action: "toggleStrike", mark: "strike", Icon: StrikethroughIcon, title: "Strikethrough" },
        ] as const
      ).map(({ action, mark, Icon, title }) => (
        <button
          key={mark}
          type="button"
          onMouseDown={(e) => { e.preventDefault(); (editor.chain().focus() as unknown as Record<string, () => unknown>)[action]?.(); }}
          className={cn(
            "flex size-7 items-center justify-center rounded-lg transition-colors hover:bg-muted",
            editor.isActive(mark) && "bg-primary text-primary-foreground hover:bg-primary/90",
          )}
          title={title}
        >
          <Icon className="size-3.5" />
        </button>
      ))}
      <div className="mx-1 h-4 w-px bg-border/70" />
      <button
        type="button"
        onMouseDown={(e) => { e.preventDefault(); editor.chain().focus().toggleCode().run(); }}
        className={cn(
          "flex size-7 items-center justify-center rounded-lg transition-colors hover:bg-muted",
          editor.isActive("code") && "bg-primary text-primary-foreground hover:bg-primary/90",
        )}
        title="Inline code"
      >
        <Code2Icon className="size-3.5" />
      </button>
    </div>
  );
}

export const BlockEditor = forwardRef<BlockEditorHandle, {
  markdown: string;
  editorJson?: Record<string, unknown> | null;
  onChange: (payload: {
    markdown: string;
    editorJson: Record<string, unknown>;
    wordCount: number;
    characterCount: number;
  }) => void;
  className?: string;
}>(function BlockEditor({
  markdown,
  editorJson,
  onChange,
  className,
}, ref) {
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        codeBlock: false,
      }),
      GlobalDragHandle.configure({
        dragHandleWidth: 20,
        scrollTreshold: 100,
      }),
      Placeholder.configure({
        placeholder: "Start writing, paste markdown, or build with the toolbar...",
      }),
      TaskList,
      TaskItem.configure({ nested: true }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
      CodeBlockLowlight.configure({ lowlight }),
      Underline,
    ],
    content: editorJson ?? markdownToHtml(markdown),
    editorProps: {
      attributes: {
        class:
          "maestro-block-editor min-h-[28rem] focus:outline-none max-w-none px-6 py-5",
      },
    },
    onUpdate: ({ editor: nextEditor }) => {
      const html = nextEditor.getHTML();
      const nextMarkdown = htmlToMarkdown(html);
      const json = nextEditor.getJSON() as Record<string, unknown>;
      const plainText = nextEditor.getText();
      onChange({
        markdown: nextMarkdown,
        editorJson: json,
        wordCount: plainText.trim().length > 0 ? plainText.trim().split(/\s+/).length : 0,
        characterCount: plainText.length,
      });
    },
  });

  useEffect(() => {
    if (!editor) {
      return;
    }
    if (editorJson) {
      const currentJson = JSON.stringify(editor.getJSON());
      const incomingJson = JSON.stringify(editorJson);
      if (currentJson !== incomingJson) {
        editor.commands.setContent(editorJson, { emitUpdate: false });
      }
      return;
    }
    const currentMarkdown = htmlToMarkdown(editor.getHTML());
    if (markdown.trim() !== currentMarkdown.trim()) {
      editor.commands.setContent(markdownToHtml(markdown), { emitUpdate: false });
    }
  }, [editor, editorJson, markdown]);

  useImperativeHandle(ref, () => ({
    getSelectionMarkdown() {
      if (!editor) {
        return "";
      }
      const { from, to, empty } = editor.state.selection;
      if (empty) {
        return "";
      }
      return editor.state.doc.textBetween(from, to, "\n").trim();
    },
    replaceSelectionMarkdown(nextMarkdown: string) {
      if (!editor) {
        return;
      }
      const { from, to, empty } = editor.state.selection;
      if (empty) {
        editor.commands.setContent(markdownToHtml(nextMarkdown));
        return;
      }
      editor
        .chain()
        .focus()
        .insertContentAt({ from, to }, markdownToHtml(nextMarkdown))
        .run();
    },
    insertMarkdown(nextMarkdown: string) {
      if (!editor) {
        return;
      }
      const { to } = editor.state.selection;
      editor
        .chain()
        .focus()
        .insertContentAt(to, markdownToHtml(nextMarkdown))
        .run();
    },
  }), [editor]);

  if (!editor) {
    return (
      <div className={cn("rounded-2xl border bg-background", className)}>
        <div className="text-muted-foreground p-6 text-sm">Loading editor...</div>
      </div>
    );
  }

  return (
    <div className={cn("overflow-hidden rounded-2xl border bg-background", className)}>
      <div className="border-b px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <ToolbarButton
            title="Heading 1"
            icon={Heading1Icon}
            active={editor.isActive("heading", { level: 1 })}
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
          />
          <ToolbarButton
            title="Heading 2"
            icon={Heading2Icon}
            active={editor.isActive("heading", { level: 2 })}
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          />
          <ToolbarButton
            title="Bullet list"
            icon={ListIcon}
            active={editor.isActive("bulletList")}
            onClick={() => editor.chain().focus().toggleBulletList().run()}
          />
          <ToolbarButton
            title="Numbered list"
            icon={ListOrderedIcon}
            active={editor.isActive("orderedList")}
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
          />
          <ToolbarButton
            title="Task list"
            icon={CheckSquareIcon}
            active={editor.isActive("taskList")}
            onClick={() => editor.chain().focus().toggleTaskList().run()}
          />
          <ToolbarButton
            title="Quote"
            icon={QuoteIcon}
            active={editor.isActive("blockquote")}
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
          />
          <ToolbarButton
            title="Code block"
            icon={Code2Icon}
            active={editor.isActive("codeBlock")}
            onClick={() => editor.chain().focus().toggleCodeBlock().run()}
          />
          <ToolbarButton
            title="Divider"
            icon={MinusIcon}
            onClick={() => editor.chain().focus().setHorizontalRule().run()}
          />
          <ToolbarButton
            title="Table"
            icon={Table2Icon}
            active={editor.isActive("table")}
            onClick={() =>
              editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
            }
          />
        </div>
      </div>
      <InlineFormatBar editor={editor} />
      <EditorContent editor={editor} />
    </div>
  );
});
