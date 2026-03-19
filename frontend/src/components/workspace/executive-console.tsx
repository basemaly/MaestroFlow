"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangleIcon,
  ArrowUpIcon,
  BotIcon,
  CopyIcon,
  DownloadIcon,
  RefreshCcwIcon,
  SquareIcon,
  WrenchIcon,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { ExecutiveIcon } from "@/components/workspace/executive-icon";
import { ExecutiveProjects } from "@/components/workspace/executive-projects";
import { Tooltip } from "@/components/workspace/tooltip";
import {
  confirmExecutiveApproval,
  executeExecutiveAction,
  executiveChat,
  getExecutiveAdvisory,
  getExecutiveApprovals,
  getExecutiveAudit,
  getExecutiveRegistry,
  getExecutiveSettings,
  getExecutiveStatus,
  previewExecutiveAction,
  rejectExecutiveApproval,
  updateExecutiveSettings,
} from "@/core/executive/api";
import type { ExecutiveActionDefinition, ExecutiveRiskLevel, ExecutiveState } from "@/core/executive/types";
import { cn } from "@/lib/utils";

const stateClasses: Record<ExecutiveState, string> = {
  healthy: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  degraded: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  unavailable: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300",
  misconfigured: "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300",
  disabled: "border-slate-500/30 bg-slate-500/10 text-slate-700 dark:text-slate-300",
  unknown: "border-muted-foreground/20 bg-muted text-muted-foreground",
};

const summaryCardAccent: Record<string, string> = {
  healthy: "border-l-4 border-l-emerald-500",
  degraded: "border-l-4 border-l-amber-500",
  unavailable: "border-l-4 border-l-red-500",
  misconfigured: "border-l-4 border-l-orange-500",
  disabled: "border-l-4 border-l-slate-500",
  unknown: "border-l-4 border-l-muted-foreground/30",
};

const summaryCountColor: Record<string, string> = {
  healthy: "text-emerald-400",
  degraded: "text-amber-400",
  unavailable: "text-red-400",
  misconfigured: "text-orange-400",
  disabled: "text-slate-400",
  unknown: "text-muted-foreground",
};

const componentBorderAccent: Record<ExecutiveState, string> = {
  healthy: "border-l-2 border-l-emerald-500/60",
  degraded: "border-l-2 border-l-amber-500/60",
  unavailable: "border-l-2 border-l-red-500/60",
  misconfigured: "border-l-2 border-l-orange-500/60",
  disabled: "border-l-2 border-l-slate-500/60",
  unknown: "border-l-2 border-l-muted-foreground/20",
};

function severityToState(severity: ExecutiveRiskLevel): ExecutiveState {
  if (severity === "critical") return "unavailable";
  if (severity === "high") return "degraded";
  if (severity === "medium") return "misconfigured";
  return "healthy";
}

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
  } catch {
    return ts;
  }
}

function formatActionLabel(actionId: string, actions: ExecutiveActionDefinition[]): string {
  const match = actions.find((item) => item.action_id === actionId);
  if (match?.label) return match.label;
  return actionId
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

type ChatTurn = { role: "user" | "assistant"; content: string };

function defaultInputForAction(action?: ExecutiveActionDefinition): string {
  if (!action) return "{}";
  switch (action.action_id) {
    case "tail_component_logs":
      return JSON.stringify({ lines: 40 }, null, 2);
    case "update_subagent_timeout":
      return JSON.stringify({ timeout_seconds: 300 }, null, 2);
    case "update_subagent_concurrency_policy":
      return JSON.stringify({ max_concurrent_subagents: 2 }, null, 2);
    default:
      return "{}";
  }
}

export function ExecutiveConsole() {
  const queryClient = useQueryClient();
  const chatAbortRef = useRef<AbortController | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const [selectedComponentId, setSelectedComponentId] = useState("litellm");
  const [selectedActionId, setSelectedActionId] = useState("recheck_component");
  const [actionInput, setActionInput] = useState("{}");
  const [previewJson, setPreviewJson] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [isChatResponding, setIsChatResponding] = useState(false);
  const [chat, setChat] = useState<ChatTurn[]>([
    {
      role: "assistant",
      content:
        "Executive is ready. Ask for system status, the next safe operational move, or a preview before you execute anything.",
    },
  ]);

  // Abort any in-flight chat request on unmount
  useEffect(() => {
    return () => {
      chatAbortRef.current?.abort();
    };
  }, []);

  // Auto-scroll chat to bottom when new messages arrive
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  const registryQuery = useQuery({
    queryKey: ["executive", "registry"],
    queryFn: getExecutiveRegistry,
    staleTime: 15_000,
  });
  const statusQuery = useQuery({
    queryKey: ["executive", "status"],
    queryFn: getExecutiveStatus,
    refetchInterval: 60_000, // Reduced from 20s: system status changes less frequently
  });
  const advisoryQuery = useQuery({
    queryKey: ["executive", "advisory"],
    queryFn: getExecutiveAdvisory,
    refetchInterval: 60_000, // Reduced from 20s: advice can be less frequent
  });
  const approvalsQuery = useQuery({
    queryKey: ["executive", "approvals"],
    queryFn: getExecutiveApprovals,
    refetchInterval: 30_000, // Reduced from 10s: approvals need refresh but not too frequent
  });
  const auditQuery = useQuery({
    queryKey: ["executive", "audit"],
    queryFn: getExecutiveAudit,
    refetchInterval: 60_000, // Reduced from 10s: audit trail is read-only historical data
  });
  const settingsQuery = useQuery({
    queryKey: ["executive", "settings"],
    queryFn: getExecutiveSettings,
    staleTime: 60_000,
  });
  const settingsMutation = useMutation({
    mutationFn: (model: string) => updateExecutiveSettings(model),
    onSuccess: (data) => {
      void queryClient.setQueryData(["executive", "settings"], data);
      toast.success(`Executive model set to ${data.model}`);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : String(error));
    },
  });

  const actions = useMemo(() => registryQuery.data?.actions ?? [], [registryQuery.data?.actions]);
  const components = useMemo(() => registryQuery.data?.components ?? [], [registryQuery.data?.components]);

  const availableActions = useMemo(
    () =>
      actions.filter((action) => {
        const component = components.find(
          (item) => item.component_id === selectedComponentId,
        );
        return component?.actions.includes(action.action_id);
      }),
    [actions, components, selectedComponentId],
  );

  const selectedAction = useMemo(
    () => availableActions.find((action) => action.action_id === selectedActionId),
    [availableActions, selectedActionId],
  );

  // Live JSON validation for the action input
  const isJsonValid = useMemo(() => {
    try {
      JSON.parse(actionInput || "{}");
      return true;
    } catch {
      return false;
    }
  }, [actionInput]);

  const invalidateExecutive = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["executive", "status"] }),
      queryClient.invalidateQueries({ queryKey: ["executive", "advisory"] }),
      queryClient.invalidateQueries({ queryKey: ["executive", "approvals"] }),
      queryClient.invalidateQueries({ queryKey: ["executive", "audit"] }),
    ]);
  };

  const previewMutation = useMutation({
    mutationFn: async () => {
      const parsed = JSON.parse(actionInput || "{}") as Record<string, unknown>;
      return previewExecutiveAction({
        action_id: selectedActionId,
        component_id: selectedComponentId,
        input: parsed,
      });
    },
    onSuccess: (result) => {
      setPreviewJson(JSON.stringify(result, null, 2));
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : String(error));
    },
  });

  const executeMutation = useMutation({
    mutationFn: async () => {
      const parsed = JSON.parse(actionInput || "{}") as Record<string, unknown>;
      return executeExecutiveAction({
        action_id: selectedActionId,
        component_id: selectedComponentId,
        input: parsed,
      });
    },
    onSuccess: async (result) => {
      setPreviewJson(JSON.stringify(result, null, 2));
      toast.message(result.summary);
      await invalidateExecutive();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : String(error));
    },
  });

  const approvalMutation = useMutation({
    mutationFn: async (payload: { approvalId: string; mode: "confirm" | "reject" }) =>
      payload.mode === "confirm"
        ? confirmExecutiveApproval(payload.approvalId)
        : rejectExecutiveApproval(payload.approvalId),
    onSuccess: async (result) => {
      toast.message(result.summary);
      await invalidateExecutive();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : String(error));
    },
  });

  const applyRecommendation = (actionId?: string | null, componentId?: string | null) => {
    if (!actionId) return;
    const targetComponent = componentId ?? selectedComponentId;
    setSelectedComponentId(targetComponent);
    setSelectedActionId(actionId);
    const next = actions.find((item) => item.action_id === actionId);
    setActionInput(defaultInputForAction(next));
  };

  const submitChat = async () => {
    const trimmed = chatInput.trim();
    if (!trimmed || isChatResponding) return;
    const nextChat = [...chat, { role: "user" as const, content: trimmed }];
    setChat(nextChat);
    setChatInput("");
    const controller = new AbortController();
    chatAbortRef.current = controller;
    setIsChatResponding(true);
    try {
      const result = await executiveChat(nextChat, controller.signal);
      setChat((current) => [...current, { role: "assistant", content: result.answer }]);
      const topRec = result.recommendations.sort((a, b) => a.priority - b.priority)[0];
      if (topRec) {
        applyRecommendation(topRec.action_id, topRec.component_id);
        if (result.recommendations.length > 1) {
          toast.message(`${result.recommendations.length} recommendations — top action loaded into console.`);
        }
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        toast.message("Executive response stopped.");
        return;
      }
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      if (chatAbortRef.current === controller) {
        chatAbortRef.current = null;
      }
      setIsChatResponding(false);
    }
  };

  const stopChat = () => {
    chatAbortRef.current?.abort();
  };

  const handleCopyMessage = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      toast.success("Response copied.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to copy response.");
    }
  };

  const handleDownloadMessage = (content: string, index: number) => {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `executive-response-${index + 1}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="grid size-full min-h-0 grid-cols-1 gap-6 p-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(22rem,0.95fr)]">
      <div className="flex min-h-0 flex-col gap-6">
        <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {Object.entries(statusQuery.data?.summary ?? {}).map(([label, count]) => (
            <Card key={label} className={cn("border-border/60 bg-background/70 py-3 overflow-hidden", summaryCardAccent[label])}>
              <CardHeader className="px-3 pb-1">
                <CardDescription className="text-[11px] uppercase tracking-[0.12em]">{label}</CardDescription>
                <CardTitle className={cn("text-xl sm:text-2xl", summaryCountColor[label])}>{count}</CardTitle>
              </CardHeader>
            </Card>
          ))}
        </section>

        <Card className="border-border/60 py-4">
          <CardHeader className="flex flex-row items-center justify-between px-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <ExecutiveIcon className="size-4" />
                System Overview
              </CardTitle>
              <CardDescription>
                Live registry-backed component health, dependencies, and suggested actions.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void invalidateExecutive()}
            >
              <RefreshCcwIcon className="size-4" />
              Refresh
            </Button>
          </CardHeader>
          <CardContent className="grid gap-3 px-4">
            {statusQuery.isLoading && (
              <div className="text-muted-foreground rounded-xl border border-dashed p-4 text-sm">
                Loading component status…
              </div>
            )}
            {(statusQuery.data?.components ?? []).map((component) => (
              <div
                key={component.component_id}
                className={cn("rounded-xl border border-border/70 bg-background/75 p-4 overflow-hidden", componentBorderAccent[component.state])}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium">{component.label}</h3>
                      <Badge
                        variant="outline"
                        className={cn("rounded-full border px-2.5 py-0.5", stateClasses[component.state])}
                      >
                        {component.state}
                      </Badge>
                    </div>
                    <p className="text-muted-foreground text-sm">{component.summary}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {component.recommended_actions.slice(0, 3).map((actionId) => (
                      <Tooltip
                        key={`${component.component_id}-${actionId}`}
                        content={
                          actions.find((item) => item.action_id === actionId)?.description ??
                          actionId
                        }
                      >
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-full"
                          onClick={() => {
                            setSelectedComponentId(component.component_id);
                            setSelectedActionId(actionId);
                            const next = actions.find((item) => item.action_id === actionId);
                            setActionInput(defaultInputForAction(next));
                          }}
                        >
                          {formatActionLabel(actionId, actions)}
                        </Button>
                      </Tooltip>
                    ))}
                  </div>
                </div>
                {component.dependencies.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    {component.dependencies.map((dependency) => (
                      <Badge
                        key={`${component.component_id}-${dependency.component_id}`}
                        variant="outline"
                        className={cn("rounded-full", stateClasses[dependency.state])}
                      >
                        {dependency.label}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
          <Card className="border-border/60 py-4">
            <CardHeader className="px-4">
              <CardTitle className="flex items-center gap-2 text-base">
                <AlertTriangleIcon className="size-4" />
                Advisory
              </CardTitle>
              <CardDescription>
                Best-practice guidance generated from live state and Executive policy.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 px-4">
              {advisoryQuery.isLoading && (
                <div className="text-muted-foreground rounded-xl border border-dashed p-4 text-sm">
                  Loading advisory…
                </div>
              )}
              {!advisoryQuery.isLoading && (advisoryQuery.data?.rules ?? []).length === 0 && (
                <div className="text-muted-foreground rounded-xl border border-dashed p-4 text-sm">
                  No active advisory warnings right now.
                </div>
              )}
              {(advisoryQuery.data?.rules ?? []).map((rule) => (
                <div key={rule.rule_id} className="rounded-xl border p-4">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className={cn("rounded-full", stateClasses[severityToState(rule.severity)])}
                    >
                      {rule.severity}
                    </Badge>
                    <div className="font-medium">{rule.title}</div>
                  </div>
                  <p className="text-muted-foreground mt-2 text-sm">{rule.summary}</p>
                  {rule.recommendation && (
                    <div className="mt-3 rounded-lg border bg-muted/30 p-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-medium">{rule.recommendation.title}</div>
                        {rule.recommendation.action_id && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="rounded-full text-xs"
                            onClick={() => applyRecommendation(rule.recommendation!.action_id, rule.recommendation!.component_id)}
                          >
                            Load in console
                          </Button>
                        )}
                      </div>
                      <div className="text-muted-foreground mt-1">{rule.recommendation.summary}</div>
                    </div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="border-border/60 py-4">
            <CardHeader className="px-4">
              <CardTitle className="flex items-center gap-2 text-base">
                <WrenchIcon className="size-4" />
                Action Console
              </CardTitle>
              <CardDescription>
                Preview and execute typed Executive actions. Risky actions create approvals.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 px-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-2 text-sm">
                  <span className="text-muted-foreground">Component</span>
                  <select
                    className="border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm"
                    value={selectedComponentId}
                    onChange={(event) => {
                      const nextComponentId = event.target.value;
                      setSelectedComponentId(nextComponentId);
                      const component = components.find((item) => item.component_id === nextComponentId);
                      const nextActionId = component?.actions[0] ?? "recheck_component";
                      setSelectedActionId(nextActionId);
                      const nextAction = actions.find((item) => item.action_id === nextActionId);
                      setActionInput(defaultInputForAction(nextAction));
                    }}
                  >
                    {components.map((component) => (
                      <option key={component.component_id} value={component.component_id}>
                        {component.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-muted-foreground">Action</span>
                  <select
                    className="border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm"
                    value={selectedActionId}
                    onChange={(event) => {
                      const nextActionId = event.target.value;
                      setSelectedActionId(nextActionId);
                      const nextAction = actions.find((item) => item.action_id === nextActionId);
                      setActionInput(defaultInputForAction(nextAction));
                    }}
                  >
                    {availableActions.map((action) => (
                      <option key={action.action_id} value={action.action_id}>
                        {action.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="space-y-1">
                <Textarea
                  value={actionInput}
                  onChange={(event) => setActionInput(event.target.value)}
                  className={cn("min-h-32 font-mono text-xs", !isJsonValid && "border-red-500/60 focus-visible:ring-red-500/30")}
                />
                {!isJsonValid && (
                  <p className="text-xs text-red-500">Invalid JSON — fix before running.</p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Tooltip content="Validate the action input and show the exact dry-run impact before anything changes.">
                  <Button
                    variant="outline"
                    className="rounded-full"
                    onClick={() => previewMutation.mutate()}
                    disabled={previewMutation.isPending || !isJsonValid}
                  >
                    Preview
                  </Button>
                </Tooltip>
                <Tooltip content="Run the selected Executive action. High-risk actions will create an approval instead of executing immediately.">
                  <Button
                    className="rounded-full"
                    onClick={() => executeMutation.mutate()}
                    disabled={executeMutation.isPending || !isJsonValid}
                  >
                    Execute
                  </Button>
                </Tooltip>
                {previewJson && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="rounded-full text-xs"
                    onClick={() => setPreviewJson(null)}
                  >
                    Clear
                  </Button>
                )}
              </div>
              {selectedAction && (
                <div className="rounded-xl border bg-muted/25 p-3 text-sm">
                  <div className="font-medium">{selectedAction.label}</div>
                  <div className="text-muted-foreground mt-1">
                    {selectedAction.description}
                  </div>
                  <div className="mt-2 flex gap-2">
                    <Badge variant="outline" className="rounded-full">
                      risk: {selectedAction.risk_level}
                    </Badge>
                    {selectedAction.requires_confirmation && (
                      <Badge variant="outline" className="rounded-full">
                        approval required
                      </Badge>
                    )}
                  </div>
                </div>
              )}
              {previewJson && (
                <pre className="overflow-x-auto rounded-xl border bg-muted/20 p-3 text-xs">
                  {previewJson}
                </pre>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="flex min-h-0 flex-col gap-6">
        <Card className="border-border/60 py-4">
          <CardHeader className="px-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BotIcon className="size-4 text-amber-500" />
                  Executive Chat
                </CardTitle>
                <CardDescription>
                  Ask for status, the right workflow, or the safest next operational move.
                </CardDescription>
              </div>
              <select
                className="border-input h-8 shrink-0 rounded-md border bg-transparent px-2 text-xs"
                value={settingsQuery.data?.model ?? ""}
                disabled={settingsMutation.isPending || settingsQuery.isLoading}
                onChange={(event) => settingsMutation.mutate(event.target.value)}
                title="Executive Agent model"
              >
                {(settingsQuery.data?.available_models ?? []).map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 px-4">
            <div className="max-h-[22rem] space-y-3 overflow-y-auto rounded-xl border bg-muted/20 p-3">
              {chat.map((message, index) => (
                <div
                  key={`chat-${index}`}
                  className={cn(
                    "relative rounded-2xl border px-4 py-3 text-sm shadow-sm",
                    message.role === "assistant"
                      ? "border-blue-900/70 bg-blue-950/90 text-blue-50"
                      : "ml-auto max-w-[90%] border-primary/20 bg-primary/10",
                  )}
                >
                  {message.role === "assistant" && (
                    <div className="-top-3.5 absolute right-3 flex items-center gap-1 rounded-full border border-blue-400/20 bg-blue-950/95 px-1.5 py-1 shadow-md">
                      <Tooltip content="Copy this Executive response to the clipboard.">
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label="Copy Executive response"
                          className="size-7 rounded-full text-blue-50 hover:bg-blue-900/80"
                          onClick={() => void handleCopyMessage(message.content)}
                        >
                          <CopyIcon className="size-3.5" />
                        </Button>
                      </Tooltip>
                      <Tooltip content="Download this Executive response as a Markdown file.">
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label="Download Executive response as Markdown"
                          className="size-7 rounded-full text-blue-50 hover:bg-blue-900/80"
                          onClick={() => handleDownloadMessage(message.content, index)}
                        >
                          <DownloadIcon className="size-3.5" />
                        </Button>
                      </Tooltip>
                    </div>
                  )}
                  <div
                    className={cn(
                      "mb-2 text-xs font-medium uppercase tracking-wide",
                      message.role === "assistant"
                        ? "text-blue-200"
                        : "text-muted-foreground",
                    )}
                  >
                    {message.role === "assistant" ? "Executive Assistant" : "User"}
                  </div>
                  <div className="whitespace-pre-wrap">{message.content}</div>
                </div>
              ))}
              <div ref={chatBottomRef} />
            </div>
            <div className="flex items-end gap-2">
              <Textarea
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                rows={6}
                className="min-h-[10rem] resize-none"
                disabled={isChatResponding}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                    event.preventDefault();
                    void submitChat();
                  }
                }}
                placeholder="What is broken? What should I use for this task? Preview a restart?"
              />
              <Tooltip
                content={
                  isChatResponding
                    ? "Stop the Executive response."
                    : "Send this message to the Executive Assistant."
                }
              >
                <Button
                  size="icon"
                  aria-label={isChatResponding ? "Stop Executive response" : "Send message to Executive Assistant"}
                  className={cn(
                    "rounded-full",
                    isChatResponding && "bg-amber-600 hover:bg-amber-700",
                  )}
                  onClick={isChatResponding ? stopChat : () => void submitChat()}
                  disabled={!isChatResponding && chatInput.trim().length === 0}
                >
                  {isChatResponding ? (
                    <SquareIcon className="size-4" />
                  ) : (
                    <ArrowUpIcon className="size-4" />
                  )}
                </Button>
              </Tooltip>
            </div>
            <div className="text-muted-foreground text-xs">
              Press Cmd+Enter or Ctrl+Enter to send. Top recommendation auto-loads into the Action Console.
            </div>
          </CardContent>
        </Card>

        <ExecutiveProjects />

        <Card className="border-border/60 py-4">
          <CardHeader className="px-4">
            <CardTitle className="text-base">Approvals</CardTitle>
            <CardDescription>
              High-risk actions wait here until a human confirms them.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 px-4">
            {(approvalsQuery.data?.approvals ?? []).length === 0 && (
              <div className="text-muted-foreground rounded-xl border border-dashed p-4 text-sm">
                No pending approvals.
              </div>
            )}
            {(approvalsQuery.data?.approvals ?? []).map((approval) => (
              <div key={approval.approval_id} className="rounded-xl border p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-medium">{approval.preview.summary}</div>
                  <Badge variant="outline" className="rounded-full">
                    {approval.status}
                  </Badge>
                </div>
                <div className="text-muted-foreground mt-2 text-sm">
                  Requested by {approval.requested_by}
                  {approval.expires_at && (
                    <span className="ml-2 text-xs">· expires {formatTimestamp(approval.expires_at)}</span>
                  )}
                </div>
                {approval.status === "pending" && (
                  <div className="mt-3 flex gap-2">
                    <Button
                      size="sm"
                      className="rounded-full"
                      onClick={() =>
                        approvalMutation.mutate({
                          approvalId: approval.approval_id,
                          mode: "confirm",
                        })
                      }
                      disabled={approvalMutation.isPending}
                    >
                      Confirm
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="rounded-full"
                      onClick={() =>
                        approvalMutation.mutate({
                          approvalId: approval.approval_id,
                          mode: "reject",
                        })
                      }
                      disabled={approvalMutation.isPending}
                    >
                      Reject
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border/60 py-4">
          <CardHeader className="px-4">
            <CardTitle className="text-base">Audit Trail</CardTitle>
            <CardDescription>
              Structured history of previews, approvals, and completed actions.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 px-4">
            {(auditQuery.data?.entries ?? []).slice(0, 12).map((entry) => (
              <div key={entry.audit_id} className="rounded-xl border p-4 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-medium">
                    {entry.action_id} → {entry.component_id}
                  </div>
                  <Badge variant="outline" className="rounded-full">
                    {entry.status}
                  </Badge>
                </div>
                <div className="text-muted-foreground mt-2">{entry.result_summary}</div>
                <div className="text-muted-foreground mt-1 text-xs">{formatTimestamp(entry.timestamp)}</div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
