"use client";

import { memo, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useWorkspaceContextPacks } from "@/components/workspace/context-packs-context";
import { OpenVikingActions } from "@/components/workspace/openviking-actions";
import {
  useActivepiecesConfig,
  useActivepiecesFlows,
  usePreviewActivepiecesFlow,
  useTriggerActivepiecesFlow,
} from "@/core/activepieces";
import { useBrowserRuntimeConfig, useBrowserRuntimeJobs, useCreateBrowserRuntimeJob } from "@/core/browser-runtime";
import type { BrowserJobAction, BrowserRuntimeChoice } from "@/core/browser-runtime";
import { useOpenVikingConfig } from "@/core/openviking";
import { useCreateStateSnapshot, useDiffStateSnapshots, useStateConfig, useStateSnapshots } from "@/core/state";
import type { StateDiffResponse, StateScope } from "@/core/state";
import { cn } from "@/lib/utils";

function statusTone(configured?: boolean, available?: boolean) {
  if (configured && available) return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  if (configured && available === false) return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
  return "border-zinc-500/30 bg-zinc-500/10 text-zinc-700 dark:text-zinc-300";
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return "{}";
  }
}

function defaultPayloadFromFlow(inputContract: Record<string, unknown> | undefined): string {
  if (!inputContract || Object.keys(inputContract).length === 0) {
    return "{}";
  }
  return safeJson(inputContract);
}

function formatRuntimeLabel(runtime: BrowserRuntimeChoice): string {
  if (runtime === "playwright") return "Playwright";
  if (runtime === "lightpanda") return "Lightpanda";
  return "Auto";
}

function formatBrowserAction(action: BrowserJobAction): string {
  if (action === "navigate") return "Navigate";
  if (action === "extract") return "Extract";
  if (action === "screenshot") return "Screenshot";
  return "Script";
}

export function ExecutiveSidecarPanel() {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <MemoizedOpenVikingCard />
      <MemoizedActivepiecesCard />
      <MemoizedBrowserRuntimeCard />
      <MemoizedStateSnapshotDiffPanel
        title="StateWeave snapshots"
        description="Snapshot and compare long-running project or experiment state."
        scope="experiment"
      />
    </div>
  );
}

function OpenVikingCard() {
  const { packs } = useWorkspaceContextPacks();
  const configQuery = useOpenVikingConfig();

  return (
    <Card className="border-border/60 bg-card/70 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          OpenViking
        </CardTitle>
        <CardDescription>Context pack registry and attachment lane.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={cn("rounded-full", statusTone(configQuery.data?.configured, configQuery.data?.available))}>
            {configQuery.data?.configured
              ? configQuery.data.available
                ? "Connected"
                : "Unavailable"
              : "Not configured"}
          </Badge>
          <Badge variant="outline" className="rounded-full">
            {packs.length} active pack{packs.length === 1 ? "" : "s"}
          </Badge>
        </div>
        <p className="text-muted-foreground text-sm">
          Attach reusable packs once and keep them visible across Composer and chat.
        </p>
        {configQuery.data?.warning ? <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-800">{configQuery.data.warning}</div> : null}
        <OpenVikingActions />
      </CardContent>
    </Card>
  );
}

function ActivepiecesCard() {
  const configQuery = useActivepiecesConfig();
  const flowsQuery = useActivepiecesFlows();
  const previewMutation = usePreviewActivepiecesFlow();
  const triggerMutation = useTriggerActivepiecesFlow();
  const [selectedFlowId, setSelectedFlowId] = useState<string>("");
  const [payload, setPayload] = useState<string>("{}");
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const selectedFlow = useMemo(
    () => flowsQuery.data?.find((flow) => flow.flow_id === selectedFlowId) ?? flowsQuery.data?.[0],
    [flowsQuery.data, selectedFlowId],
  );

  useEffect(() => {
    if (!selectedFlow) {
      return;
    }
    if (!selectedFlowId) {
      setSelectedFlowId(selectedFlow.flow_id);
    }
  }, [selectedFlow, selectedFlowId]);

  useEffect(() => {
    if (!selectedFlow) {
      return;
    }
    setPayload((current) => {
      if (current.trim() === "{}" || !current.trim()) {
        return defaultPayloadFromFlow(selectedFlow.input_contract);
      }
      return current;
    });
  }, [selectedFlow]);

  const payloadValue = useMemo(() => {
    try {
      return JSON.parse(payload || "{}") as Record<string, unknown>;
    } catch {
      return null;
    }
  }, [payload]);

  return (
    <Card className="border-border/60 bg-card/70 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">Activepieces</CardTitle>
        <CardDescription>Approved flow runner and inbound automation bridge.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={cn("rounded-full", statusTone(configQuery.data?.configured, configQuery.data?.available))}>
            {configQuery.data?.configured
              ? configQuery.data.available
                ? "Connected"
                : "Unavailable"
              : "Not configured"}
          </Badge>
          <Badge variant="outline" className="rounded-full">
            {(flowsQuery.data?.length ?? 0)} flow{(flowsQuery.data?.length ?? 0) === 1 ? "" : "s"}
          </Badge>
        </div>
        <Select value={selectedFlowId} onValueChange={setSelectedFlowId}>
          <SelectTrigger className="bg-background/70">
            <SelectValue placeholder="Select an approved flow" />
          </SelectTrigger>
          <SelectContent>
            {(flowsQuery.data ?? []).map((flow) => (
              <SelectItem key={flow.flow_id} value={flow.flow_id}>
                {flow.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {selectedFlow ? (
          <div className="rounded-2xl border border-border/60 bg-background/70 p-3 text-sm">
            <div className="font-medium">{selectedFlow.label}</div>
            <div className="text-muted-foreground mt-1 text-xs">{selectedFlow.description}</div>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant="outline" className="rounded-full text-[10px]">
                approval {selectedFlow.approval_required ? "required" : "optional"}
              </Badge>
              <Badge variant="outline" className="rounded-full text-[10px]">
                {selectedFlow.enabled ? "enabled" : "disabled"}
              </Badge>
            </div>
          </div>
        ) : null}
        <Textarea
          value={payload}
          onChange={(event) => setPayload(event.target.value)}
          className="min-h-28 font-mono text-xs"
        />
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            className="rounded-full"
            disabled={!selectedFlowId || previewMutation.isPending || payloadValue === null}
            onClick={() =>
              previewMutation.mutate(
                { flowId: selectedFlowId, payload: payloadValue ?? {} },
                {
                  onSuccess: (result) => {
                    setPreview(result as unknown as Record<string, unknown>);
                    if (result.warning) {
                      toast.warning(result.warning);
                    }
                  },
                  onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
                },
              )
            }
          >
            Preview
          </Button>
          <Button
            size="sm"
            className="rounded-full"
            disabled={!selectedFlowId || triggerMutation.isPending || payloadValue === null}
            onClick={() =>
              triggerMutation.mutate(
                { flowId: selectedFlowId, payload: payloadValue ?? {} },
                {
                  onSuccess: (result) => {
                    if (result.warning) {
                      toast.warning(result.warning);
                    } else {
                      toast.success(result.summary);
                    }
                    setPreview(result as unknown as Record<string, unknown>);
                  },
                  onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
                },
              )
            }
          >
            Trigger
          </Button>
        </div>
        {preview ? (
          <pre className="max-h-48 overflow-auto rounded-2xl border border-border/60 bg-muted/20 p-3 text-xs">
            {safeJson(preview)}
          </pre>
        ) : null}
      </CardContent>
    </Card>
  );
}

function BrowserRuntimeCard() {
  const configQuery = useBrowserRuntimeConfig();
  const jobsQuery = useBrowserRuntimeJobs();
  const createMutation = useCreateBrowserRuntimeJob();
  const [runtime, setRuntime] = useState<BrowserRuntimeChoice>("auto");
  const [action, setAction] = useState<BrowserJobAction>("navigate");
  const [url, setUrl] = useState("");
  const [target, setTarget] = useState("");
  const [input, setInput] = useState("{}");
  const latestJobs = jobsQuery.data ?? [];

  const parsedInput = useMemo(() => {
    try {
      return JSON.parse(input || "{}") as Record<string, unknown>;
    } catch {
      return null;
    }
  }, [input]);

  return (
    <Card className="border-border/60 bg-card/70 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">Browser runtime</CardTitle>
        <CardDescription>Route browser jobs through Playwright or Lightpanda.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={cn("rounded-full", statusTone(configQuery.data?.configured, configQuery.data?.available))}>
            {configQuery.data?.configured
              ? configQuery.data.available
                ? "Connected"
                : "Unavailable"
              : "Not configured"}
          </Badge>
          <Badge variant="outline" className="rounded-full">
            default {configQuery.data?.default_runtime ? formatRuntimeLabel(configQuery.data.default_runtime) : "Auto"}
          </Badge>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Select value={runtime} onValueChange={(value) => setRuntime(value as BrowserRuntimeChoice)}>
            <SelectTrigger className="bg-background/70">
              <SelectValue placeholder="Runtime" />
            </SelectTrigger>
            <SelectContent>
              {(configQuery.data?.supported_runtimes ?? ["auto", "playwright", "lightpanda"]).map((choice) => (
                <SelectItem key={choice} value={choice}>
                  {formatRuntimeLabel(choice)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={action} onValueChange={(value) => setAction(value as BrowserJobAction)}>
            <SelectTrigger className="bg-background/70">
              <SelectValue placeholder="Action" />
            </SelectTrigger>
            <SelectContent>
              {(["navigate", "extract", "screenshot", "script"] as BrowserJobAction[]).map((choice) => (
                <SelectItem key={choice} value={choice}>
                  {formatBrowserAction(choice)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="Target URL" />
        <Input value={target} onChange={(event) => setTarget(event.target.value)} placeholder="Target / selector / job label (optional)" />
        <Textarea value={input} onChange={(event) => setInput(event.target.value)} className="min-h-28 font-mono text-xs" />
        <Button
          size="sm"
          className="rounded-full"
          disabled={createMutation.isPending || parsedInput === null || (!url.trim() && !target.trim())}
          onClick={() =>
            createMutation.mutate(
              {
                runtime,
                action,
                url: url.trim() || undefined,
                target: target.trim() || undefined,
                input: parsedInput ?? {},
              },
              {
                onSuccess: (result) => {
                  if (result.warning) {
                    toast.warning(result.warning);
                  } else {
                    toast.success(result.job.summary);
                  }
                },
                onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
              },
            )
          }
        >
          Run job
        </Button>
        {latestJobs.length > 0 ? (
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Recent jobs</div>
            <ScrollArea className="max-h-52 rounded-2xl border border-border/60">
              <div className="space-y-2 p-3">
                {latestJobs.slice(0, 4).map((job) => (
                  <div key={job.job_id} className="rounded-2xl border border-border/60 bg-background/70 p-3 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-medium">{job.summary}</div>
                      <Badge variant="outline" className="rounded-full text-[10px]">
                        {job.status}
                      </Badge>
                    </div>
                    <div className="text-muted-foreground mt-1">
                      {job.runtime} · {job.action}
                      {job.url ? ` · ${job.url}` : ""}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function StateSnapshotDiffPanel({
  title,
  description,
  scope,
  referenceId,
  compact = false,
}: {
  title: string;
  description: string;
  scope: StateScope;
  referenceId?: string;
  compact?: boolean;
}) {
  const configQuery = useStateConfig();
  const [manualReferenceId, setManualReferenceId] = useState(referenceId ?? "");
  const effectiveReferenceId = referenceId ?? manualReferenceId.trim();
  const snapshotsQuery = useStateSnapshots({
    scope,
    reference_id: effectiveReferenceId || undefined,
    limit: 12,
  });
  const diffMutation = useDiffStateSnapshots();
  const createSnapshotMutation = useCreateStateSnapshot();
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");
  const [diff, setDiff] = useState<StateDiffResponse | null>(null);
  const snapshots = useMemo(() => snapshotsQuery.data?.snapshots ?? [], [snapshotsQuery.data?.snapshots]);

  useEffect(() => {
    if (!leftId && snapshots[0]?.snapshot_id) {
      setLeftId(snapshots[0].snapshot_id);
    }
    if (!rightId && snapshots[1]?.snapshot_id) {
      setRightId(snapshots[1].snapshot_id);
    }
  }, [leftId, rightId, snapshots]);

  const snapshotOptions = useMemo(
    () =>
      snapshots.map((snapshot) => ({
        id: snapshot.snapshot_id,
        label: snapshot.label,
        summary: snapshot.summary ?? snapshot.state_type ?? snapshot.scope,
      })),
    [snapshots],
  );

  return (
    <Card className={cn("border-border/60 bg-card/70 shadow-sm", compact && "h-full")}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={cn("rounded-full", statusTone(configQuery.data?.configured, configQuery.data?.available))}>
            {configQuery.data?.configured
              ? configQuery.data.available
                ? "Connected"
                : "Unavailable"
              : "Not configured"}
          </Badge>
          <Badge variant="outline" className="rounded-full">
            {scope}
          </Badge>
        </div>
        {!referenceId ? (
          <Input
            value={manualReferenceId}
            onChange={(event) => setManualReferenceId(event.target.value)}
            placeholder="Reference ID"
          />
        ) : null}
        <div className="grid gap-3 sm:grid-cols-2">
          <Select value={leftId} onValueChange={setLeftId}>
            <SelectTrigger className="bg-background/70">
              <SelectValue placeholder="Left snapshot" />
            </SelectTrigger>
            <SelectContent>
              {snapshotOptions.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={rightId} onValueChange={setRightId}>
            <SelectTrigger className="bg-background/70">
              <SelectValue placeholder="Right snapshot" />
            </SelectTrigger>
            <SelectContent>
              {snapshotOptions.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            className="rounded-full"
            disabled={!effectiveReferenceId || createSnapshotMutation.isPending}
            onClick={() =>
              createSnapshotMutation.mutate(
                {
                  scope,
                  reference_id: effectiveReferenceId || undefined,
                  label: `${title} snapshot`,
                  summary: description,
                  metadata: {
                    source: "frontend",
                    category: scope,
                  },
                },
                {
                  onSuccess: () => {
                    toast.success("Snapshot saved");
                    void snapshotsQuery.refetch();
                  },
                  onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
                },
              )
            }
          >
            Snapshot
          </Button>
          <Button
            size="sm"
            className="rounded-full"
            disabled={!leftId || !rightId || diffMutation.isPending}
            onClick={() =>
              diffMutation.mutate(
                { left_snapshot_id: leftId, right_snapshot_id: rightId },
                {
                  onSuccess: (result) => {
                    setDiff(result);
                    if (result.warning) {
                      toast.warning(result.warning);
                    }
                  },
                  onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
                },
              )
            }
          >
            Diff
          </Button>
        </div>
        {snapshotsQuery.data?.warning ? <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-800">{snapshotsQuery.data.warning}</div> : null}
        <ScrollArea className="max-h-48 rounded-2xl border border-border/60">
          <div className="space-y-2 p-3">
            {snapshots.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/60 bg-muted/10 p-4 text-sm text-muted-foreground">
                No snapshots loaded yet.
              </div>
            ) : (
              snapshots.map((snapshot) => (
                <div key={snapshot.snapshot_id} className="rounded-2xl border border-border/60 bg-background/70 p-3 text-xs">
                  <div className="font-medium">{snapshot.label}</div>
                  <div className="text-muted-foreground mt-1">
                    {snapshot.summary ?? snapshot.state_type ?? "Snapshot"} · {snapshot.created_at}
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
        {diff ? (
          <div className="rounded-2xl border border-border/60 bg-muted/20 p-3">
            <div className="font-medium">{diff.summary}</div>
            <div className="text-muted-foreground mt-1 text-xs">
              {diff.left_snapshot_id} → {diff.right_snapshot_id}
            </div>
            <ScrollArea className="mt-3 max-h-48">
              <div className="space-y-2">
                {diff.changes.length === 0 ? (
                  <div className="text-muted-foreground text-sm">No differences reported.</div>
                ) : (
                  diff.changes.slice(0, 20).map((change) => (
                    <div key={`${change.path}-${change.change_type}`} className="rounded-xl border border-border/60 bg-background/70 p-2 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-medium">{change.path}</div>
                        <Badge variant="outline" className="rounded-full text-[10px]">
                          {change.change_type}
                        </Badge>
                      </div>
                      {change.summary ? <div className="text-muted-foreground mt-1">{change.summary}</div> : null}
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

// Memoized versions for optimal sidebar re-render performance
const MemoizedOpenVikingCard = memo(OpenVikingCard);
const MemoizedActivepiecesCard = memo(ActivepiecesCard);
const MemoizedBrowserRuntimeCard = memo(BrowserRuntimeCard);
const MemoizedStateSnapshotDiffPanel = memo(StateSnapshotDiffPanel);
