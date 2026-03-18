"use client";

import { ShieldCheckIcon, XIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ExecutiveProjects } from "@/components/workspace/executive-projects";

export function ExecutiveDrawerTrigger({
  isSidebarOpen,
  asFab = false,
}: {
  isSidebarOpen: boolean;
  asFab?: boolean;
}) {
  const [open, setOpen] = useState(false);

  const fabButton = (
    <button
      onClick={() => setOpen(true)}
      title="Executive Agent"
      className="flex size-12 items-center justify-center rounded-full bg-amber-500 text-black shadow-lg ring-2 ring-amber-400/30 transition-all hover:bg-amber-400 hover:scale-105 active:scale-95"
    >
      <ShieldCheckIcon className="size-5" />
    </button>
  );

  const sidebarButton = (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={() => setOpen(true)}
          className="group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          <ShieldCheckIcon className="size-4 shrink-0 text-amber-500 group-hover:text-amber-400" />
          {isSidebarOpen && (
            <span className="truncate font-medium">Quick Access</span>
          )}
        </button>
      </TooltipTrigger>
      {!isSidebarOpen && (
        <TooltipContent side="right">Executive Agent</TooltipContent>
      )}
    </Tooltip>
  );

  return (
    <>
      {asFab ? fabButton : sidebarButton}

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          side="right"
          className="flex w-full flex-col gap-0 p-0 sm:max-w-2xl"
        >
          <SheetHeader className="flex flex-row items-center justify-between border-b px-4 py-3">
            <SheetTitle className="flex items-center gap-2 text-base">
              <ShieldCheckIcon className="size-4 text-amber-500" />
              Executive Agent
            </SheetTitle>
            <button
              onClick={() => setOpen(false)}
              className="rounded-sm text-muted-foreground opacity-70 transition-opacity hover:opacity-100"
            >
              <XIcon className="size-4" />
            </button>
          </SheetHeader>
          <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-4">
            <ExecutiveProjects />
            <ExecutiveQuickChat onClose={() => setOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}

function ExecutiveQuickChat({ onClose }: { onClose: () => void }) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<
    Array<{ role: "user" | "assistant"; content: string }>
  >([]);
  const [loading, setLoading] = useState(false);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    const next = [...messages, { role: "user" as const, content: text }];
    setMessages(next);
    setLoading(true);
    try {
      const { executiveChat } = await import("@/core/executive/api");
      const result = await executiveChat(
        next.map((m) => ({ role: m.role, content: m.content })),
      );
      setMessages([...next, { role: "assistant", content: result.answer }]);
    } catch (err) {
      setMessages([
        ...next,
        { role: "assistant", content: `Error: ${String(err)}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-border/60 bg-background/70 flex flex-col gap-0 overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border/40 px-4 py-2.5">
        <ShieldCheckIcon className="size-3.5 text-amber-500" />
        <span className="text-sm font-medium">Executive Chat</span>
      </div>

      {/* Message history */}
      <div className="flex min-h-[120px] max-h-80 flex-col gap-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="text-xs text-muted-foreground">
            Ask what&apos;s broken, what workflow to use, or create a project.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed ${
                m.role === "user"
                  ? "bg-amber-500/20 text-amber-100 dark:bg-amber-500/30"
                  : "border border-border/50 bg-muted/40 text-foreground"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-xl border border-border/50 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              Thinking…
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border/40 p-3 flex gap-2">
        <textarea
          className="min-h-[56px] flex-1 resize-none rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-amber-500/50"
          placeholder="Ask the Executive Agent…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              void send();
            }
          }}
        />
        <Button
          size="sm"
          className="self-end bg-amber-500 text-black hover:bg-amber-400"
          onClick={() => void send()}
          disabled={loading || !input.trim()}
        >
          Send
        </Button>
      </div>
    </div>
  );
}
