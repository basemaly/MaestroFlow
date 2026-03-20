"use client";

import { ClipboardIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { Tooltip } from "./tooltip";

export function ClipboardPasteButton({
  className,
  tooltip = "Paste text from the clipboard.",
  ariaLabel = "Paste from clipboard",
  onPasteText,
  variant = "outline",
  size = "sm",
}: {
  className?: string;
  tooltip?: string;
  ariaLabel?: string;
  onPasteText: (text: string) => void;
  variant?: "default" | "outline" | "ghost" | "secondary";
  size?: "sm" | "icon" | "icon-sm";
}) {
  const [isReading, setIsReading] = useState(false);

  const handlePaste = async () => {
    try {
      setIsReading(true);
      const text = await navigator.clipboard.readText();
      if (!text.trim()) {
        toast.message("Clipboard is empty.");
        return;
      }
      onPasteText(text);
      toast.success("Pasted from clipboard.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Clipboard paste failed.");
    } finally {
      setIsReading(false);
    }
  };

  return (
    <Tooltip content={tooltip}>
      <Button
        type="button"
        variant={variant}
        size={size}
        aria-label={ariaLabel}
        className={cn("rounded-full", className)}
        onClick={() => void handlePaste()}
        disabled={isReading}
      >
        <ClipboardIcon className="size-3.5" />
      </Button>
    </Tooltip>
  );
}
