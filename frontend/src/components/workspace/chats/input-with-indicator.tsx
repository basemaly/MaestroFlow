"use client";

import { Loader2Icon } from "lucide-react";
import { forwardRef } from "react";

import { Textarea } from "@/components/ui/textarea";

interface InputWithIndicatorProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  isLoading?: boolean;
  isThinking?: boolean;
}

export const InputWithIndicator = forwardRef<HTMLTextAreaElement, InputWithIndicatorProps>(
  ({ isLoading, isThinking, ...props }, ref) => {
    return (
      <div className="relative">
        {/* eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing */}
        <Textarea ref={ref} {...props} disabled={isLoading || isThinking || props.disabled} />
        {/* eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing */}
        {(isLoading || isThinking) && (
          <div className="absolute right-3 bottom-3 flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
            <Loader2Icon className="size-3 animate-spin" />
            <span>{isThinking ? "Thinking..." : "Processing..."}</span>
          </div>
        )}
      </div>
    );
  },
);

InputWithIndicator.displayName = "InputWithIndicator";
