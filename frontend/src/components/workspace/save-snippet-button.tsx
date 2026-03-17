"use client";

import { BookmarkIcon, BookmarkCheckIcon } from "lucide-react";
import { useCallback, useState, type ComponentProps } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useSnippets } from "@/core/snippets";

import { Tooltip } from "./tooltip";

export function SaveSnippetButton({
  text,
  sourceThreadId,
  ...props
}: ComponentProps<typeof Button> & {
  text: string;
  sourceThreadId?: string;
}) {
  const { addSnippet } = useSnippets();
  const [saved, setSaved] = useState(false);

  const handleSave = useCallback(() => {
    if (!text.trim()) return;
    addSnippet(text, undefined, undefined, sourceThreadId);
    setSaved(true);
    toast.success("Saved to Snippet Shelf");
    setTimeout(() => setSaved(false), 2000);
  }, [text, sourceThreadId, addSnippet]);

  return (
    <Tooltip content="Save to Snippets">
      <Button
        size="icon-sm"
        type="button"
        variant="ghost"
        onClick={handleSave}
        {...props}
      >
        {saved ? (
          <BookmarkCheckIcon className="text-green-500" size={12} />
        ) : (
          <BookmarkIcon size={12} />
        )}
      </Button>
    </Tooltip>
  );
}
