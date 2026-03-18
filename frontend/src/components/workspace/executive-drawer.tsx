"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLinkIcon, Loader2Icon, PlayIcon, SquareIcon } from "lucide-react";
import { XIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { AgentPresetMenu } from "@/components/workspace/context-controls";
import { ExecutiveIcon } from "@/components/workspace/executive-icon";
import { ExecutiveProjects } from "@/components/workspace/executive-projects";
import { cancelProject, launchExecutiveAgentRun, listProjects } from "@/core/executive/api";

export function ExecutiveDrawerTrigger({
  isSidebarOpen,
  variant = "sidebar",
}: {
  isSidebarOpen: boolean;
  variant?: "sidebar" | "header" | "fab";
}) {
  const [open, setOpen] = useState(false);

  const fabButton = (
    <button
      onClick={() => setOpen(true)}
      title="Executive Agent"
      className="flex size-12 items-center justify-center rounded-full bg-amber-500 text-black shadow-lg ring-2 ring-amber-400/30 transition-all hover:bg-amber-400 hover:scale-105 active:scale-95"
    >
      <ExecutiveIcon className="size-5 text-black" />
    </button>
  );

  const headerButton = (
    <Button
      size="sm"
      variant="ghost"
      className="h-9 w-9 border border-amber-500/25 bg-amber-500/10 px-0 text-amber-700 hover:bg-amber-500/18 hover:text-amber-800 dark:text-amber-200 dark:hover:text-amber-100"
      onClick={() => setOpen(true)}
      title="Executive Agent"
      aria-label="Executive Agent"
    >
      <ExecutiveIcon className="text-lg" />
    </Button>
  );

  const sidebarButton = (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={() => setOpen(true)}
          className="group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          <ExecutiveIcon className="size-4 shrink-0 text-amber-500 group-hover:text-amber-400" />
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
      {variant === "fab"
        ? fabButton
        : variant === "header"
          ? headerButton
          : sidebarButton}

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          side="right"
          className="flex w-full flex-col gap-0 p-0 sm:max-w-2xl"
        >
          <SheetHeader className="flex flex-row items-center justify-between border-b px-4 py-3">
            <div className="space-y-1">
              <SheetTitle className="flex items-center gap-2 text-base">
                <ExecutiveIcon className="size-4" />
                Executive Agent
              </SheetTitle>
              <SheetDescription>
                Monitor system health, launch specialist runs, and stop active workflows from one control surface.
              </SheetDescription>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="rounded-sm text-muted-foreground opacity-70 transition-opacity hover:opacity-100"
            >
              <XIcon className="size-4" />
            </button>
          </SheetHeader>
          <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-4">
            <ExecutiveAgentLifecycle />
            <ExecutiveProjects />
            <ExecutiveQuickChat />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}

function ExecutiveAgentLifecycle() {
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [agentName, setAgentName] = useState<string | undefined>(undefined);
  const [mode, setMode] = useState<"standard" | "pro" | "ultra">("pro");
  const [lastThreadId, setLastThreadId] = useState<string | null>(null);
  const [stoppingProjectId, setStoppingProjectId] = useState<string | null>(null);

  const quickPrompts = [
    "Audit the current document workflow and recommend one simplification.",
    "Review active warnings and tell me what actually needs attention.",
    "Summarize where the current thread is stuck and propose the next move.",
  ];

  const projectsQuery = useQuery({
    queryKey: ["executive", "projects", "drawer"],
    queryFn: () => listProjects(),
    staleTime: 15_000,
    refetchInterval: 15_000,
  });

  const launchMutation = useMutation({
    mutationFn: () =>
      launchExecutiveAgentRun({
        prompt: prompt.trim(),
        agent_name: agentName,
        mode,
        thinking_enabled: mode !== "standard",
        subagent_enabled: mode === "ultra",
      }),
    onSuccess: (result) => {
      if (result.thread_id) {
        setLastThreadId(result.thread_id);
        toast.success("Agent thread launched");
      } else {
        toast.error(result.error ?? "Agent run failed");
      }
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
  });

  const stopMutation = useMutation({
    mutationFn: (projectId: string) => cancelProject(projectId),
    onSuccess: () => {
      setStoppingProjectId(null);
      toast.success("Workflow stopped");
      void queryClient.invalidateQueries({ queryKey: ["executive", "projects"] });
    },
    onError: (error) => {
      setStoppingProjectId(null);
      toast.error(error instanceof Error ? error.message : String(error));
    },
  });

  const activeProjects =
    projectsQuery.data?.projects.filter((project) =>
      ["running", "waiting_approval", "paused"].includes(project.status),
    ) ?? [];

  return (
    <Card className="border-amber-500/20 bg-amber-500/5">
      <CardHeader className="space-y-1 pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <ExecutiveIcon className="size-4" />
          Agent Lifecycle
        </CardTitle>
        <CardDescription>
          Launch specialist runs from Executive, then stop active workflows when they are no longer worth the spend.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <AgentPresetMenu
            value={agentName}
            onChange={setAgentName}
            compact
          />
          <Button
            size="sm"
            variant={mode === "standard" ? "secondary" : "outline"}
            onClick={() => setMode("standard")}
          >
            Standard
          </Button>
          <Button
            size="sm"
            variant={mode === "pro" ? "secondary" : "outline"}
            onClick={() => setMode("pro")}
          >
            Pro
          </Button>
          <Button
            size="sm"
            variant={mode === "ultra" ? "secondary" : "outline"}
            onClick={() => setMode("ultra")}
          >
            Ultra
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {quickPrompts.map((template) => (
            <Button
              key={template}
              size="sm"
              type="button"
              variant="ghost"
              className="h-auto whitespace-normal rounded-full border border-border/60 px-3 py-1.5 text-left text-xs text-muted-foreground"
              onClick={() => setPrompt(template)}
            >
              {template}
            </Button>
          ))}
        </div>
        <textarea
          className="min-h-[92px] w-full resize-none rounded-lg border border-border/50 bg-background/80 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          placeholder="Spawn a specialist run. Example: Audit the current Drafting workflow and recommend one simplification."
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />
        <div className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span>{mode === "standard" ? "Fastest, lowest overhead." : mode === "pro" ? "Balanced planning and execution." : "Deepest run with subagents enabled."}</span>
          {agentName ? <span>Preset: {agentName}</span> : <span>Using default MaestroFlow lead agent.</span>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            className="bg-amber-500 text-black hover:bg-amber-400"
            disabled={launchMutation.isPending || !prompt.trim()}
            onClick={() => launchMutation.mutate()}
          >
            {launchMutation.isPending ? (
              <Loader2Icon className="size-4 animate-spin" />
            ) : (
              <PlayIcon className="size-4" />
            )}
            Launch Agent
          </Button>
          {lastThreadId ? (
            <Button size="sm" variant="outline" asChild>
              <Link href={agentName ? `/workspace/agents/${agentName}/chats/${lastThreadId}` : `/workspace/chats/${lastThreadId}`}>
                <ExternalLinkIcon className="size-4" />
                Open Thread
              </Link>
            </Button>
          ) : null}
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium">Active workflows</div>
            <div className="text-muted-foreground text-xs">
              {activeProjects.length} live
            </div>
          </div>
          {activeProjects.length === 0 ? (
            <div className="text-muted-foreground rounded-lg border border-dashed px-3 py-2 text-xs">
              No active Executive workflows right now.
            </div>
          ) : (
            <div className="space-y-2">
              {activeProjects.map((project) => (
                <div
                  key={project.project_id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border/50 bg-background/70 px-3 py-2"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">{project.title}</div>
                    <div className="text-muted-foreground text-xs">
                      {project.status} · stage {project.current_stage_index + 1} of {project.total_stages}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-muted-foreground"
                    disabled={stopMutation.isPending}
                    onClick={() => {
                      setStoppingProjectId(project.project_id);
                      stopMutation.mutate(project.project_id);
                    }}
                  >
                    {stopMutation.isPending && stoppingProjectId === project.project_id ? (
                      <Loader2Icon className="size-3.5 animate-spin" />
                    ) : (
                      <SquareIcon className="size-3.5" />
                    )}
                    Stop
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ExecutiveQuickChat() {
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
        <ExecutiveIcon className="size-3.5" />
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
