"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BotIcon,
  CheckCircle2Icon,
  ChevronDownIcon,
  ChevronRightIcon,
  CircleDotIcon,
  ClockIcon,
  FolderKanbanIcon,
  Loader2Icon,
  PauseIcon,
  PlayIcon,
  RefreshCwIcon,
  XCircleIcon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  advanceProject,
  approveProjectCheckpoint,
  cancelProject,
  getProject,
  listProjects,
} from "@/core/executive/api";
import type { CheckpointInfo, ProjectStatus, ProjectSummary, StageInfo, StageStatus } from "@/core/executive/types";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Status styles
// ---------------------------------------------------------------------------

const projectStatusClasses: Record<ProjectStatus, string> = {
  planning: "border-muted/40 bg-muted/20 text-muted-foreground",
  waiting_approval: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  running: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300",
  paused: "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300",
  completed: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  cancelled: "border-muted/40 bg-muted/20 text-muted-foreground line-through",
  failed: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300",
};

const stageStatusIcon: Record<StageStatus, React.ReactNode> = {
  pending: <CircleDotIcon className="size-3.5 text-muted-foreground" />,
  waiting_approval: <PauseIcon className="size-3.5 text-amber-500" />,
  running: <Loader2Icon className="size-3.5 animate-spin text-blue-500" />,
  completed: <CheckCircle2Icon className="size-3.5 text-emerald-500" />,
  skipped: <CircleDotIcon className="size-3.5 text-muted-foreground/50" />,
  failed: <XCircleIcon className="size-3.5 text-red-500" />,
};

function formatTs(ts?: string | null): string {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
  } catch {
    return ts;
  }
}

// ---------------------------------------------------------------------------
// Stage timeline row
// ---------------------------------------------------------------------------

function StageRow({ stage }: { stage: StageInfo }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="space-y-1">
      <button
        className="flex w-full items-center gap-2 rounded-md px-1 py-1 text-sm hover:bg-muted/30"
        onClick={() => setExpanded((v) => !v)}
      >
        {stageStatusIcon[stage.status]}
        <span className="flex-1 text-left font-medium">{stage.title}</span>
        <span className="text-muted-foreground text-xs capitalize">{stage.kind}</span>
        {stage.agent_id && (
          <span className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-muted/40 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            <BotIcon className="size-2.5" />
            {stage.agent_id}
          </span>
        )}
        {stage.iteration_count > 0 && (
          <span className="text-muted-foreground text-xs">
            {stage.iteration_count}/{stage.max_iterations}
          </span>
        )}
        {expanded ? <ChevronDownIcon className="size-3.5" /> : <ChevronRightIcon className="size-3.5" />}
      </button>
      {expanded && stage.output_preview && (
        <div className="border-border/40 ml-5 rounded-md border bg-muted/20 p-2 text-xs font-mono whitespace-pre-wrap break-words">
          {stage.output_preview}
          {(stage.current_output?.length ?? 0) > (stage.output_preview?.length ?? 0) && (
            <span className="text-muted-foreground"> [truncated]</span>
          )}
        </div>
      )}
      {expanded && stage.error && (
        <div className="ml-5 rounded-md border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-700 dark:text-red-300">
          {stage.error}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Project detail card (expanded)
// ---------------------------------------------------------------------------

function ProjectDetail({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();

  const projectQuery = useQuery({
    queryKey: ["executive", "projects", projectId],
    queryFn: () => getProject(projectId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      // Reduced intervals: running 8s→15s, approval 15s→30s, other 30s→60s
      if (status === "running") return 15_000; // More breathing room for running projects
      if (status === "waiting_approval") return 30_000; // Approval status is important but not urgent
      return 60_000; // Completed/idle projects checked less frequently
    },
  });

  const advanceMutation = useMutation({
    mutationFn: () => advanceProject(projectId),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["executive", "projects"] });
      if (result.status === "waiting_approval") {
        toast.info(`Checkpoint: ${result.message}`);
      } else {
        toast.success(result.message);
      }
    },
    onError: (err) => toast.error(String(err)),
  });

  const approveMutation = useMutation({
    mutationFn: (checkpointId: string) => approveProjectCheckpoint(projectId, checkpointId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["executive", "projects"] });
      toast.success("Checkpoint approved");
    },
    onError: (err) => toast.error(String(err)),
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelProject(projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["executive", "projects"] });
      toast.success("Project cancelled");
    },
    onError: (err) => toast.error(String(err)),
  });

  const project = projectQuery.data;

  if (projectQuery.isLoading) {
    return <div className="py-4 text-center text-sm text-muted-foreground">Loading…</div>;
  }
  if (!project) return null;

  const pendingCheckpoints = (project.checkpoints ?? []).filter((cp: CheckpointInfo) => cp.status === "pending");
  const isActive = project.status === "running" || project.status === "waiting_approval";

  return (
    <div className="space-y-3 pt-2">
      {/* Goal */}
      <p className="text-muted-foreground text-xs">{project.goal}</p>

      {/* Pending checkpoints */}
      {pendingCheckpoints.map((cp: CheckpointInfo) => (
        <div
          key={cp.checkpoint_id}
          className="flex items-start justify-between gap-3 rounded-md border border-amber-500/30 bg-amber-500/10 p-3"
        >
          <div className="space-y-0.5">
            <p className="text-sm font-medium text-amber-700 dark:text-amber-300">{cp.title}</p>
            <p className="text-muted-foreground text-xs">{cp.description}</p>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="shrink-0 border-amber-500/40 text-amber-700 dark:text-amber-300"
            onClick={() => approveMutation.mutate(cp.checkpoint_id)}
            disabled={approveMutation.isPending}
          >
            {approveMutation.isPending ? <Loader2Icon className="size-3 animate-spin" /> : "Approve"}
          </Button>
        </div>
      ))}

      {/* Stage timeline */}
      <div className="space-y-0.5">
        {(project.stages ?? []).map((stage: StageInfo) => (
          <StageRow key={stage.stage_id} stage={stage} />
        ))}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 pt-1">
        {isActive && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => advanceMutation.mutate()}
            disabled={advanceMutation.isPending}
          >
            {advanceMutation.isPending ? (
              <Loader2Icon className="size-3 animate-spin" />
            ) : (
              <PlayIcon className="size-3" />
            )}
            Advance
          </Button>
        )}
        {project.status !== "cancelled" && project.status !== "completed" && (
          <Button
            size="sm"
            variant="ghost"
            className="text-muted-foreground"
            onClick={() => {
              if (confirm("Cancel this project?")) cancelMutation.mutate();
            }}
            disabled={cancelMutation.isPending}
          >
            Cancel
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          className="text-muted-foreground"
          onClick={() => void queryClient.invalidateQueries({ queryKey: ["executive", "projects", projectId] })}
        >
          <RefreshCwIcon className="size-3" />
        </Button>
      </div>

      {/* Timestamps */}
      <div className="text-muted-foreground flex gap-4 text-xs">
        {project.started_at && <span>Started {formatTs(project.started_at)}</span>}
        {project.completed_at && <span>Completed {formatTs(project.completed_at)}</span>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Project summary row (collapsed)
// ---------------------------------------------------------------------------

function ProjectRow({ project }: { project: ProjectSummary }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-border/60 bg-background/70 p-4">
      <button className="flex w-full items-start gap-3" onClick={() => setExpanded((v) => !v)}>
        <div className="flex-1 space-y-1 text-left">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{project.title}</span>
            <Badge
              variant="outline"
              className={cn("rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide", projectStatusClasses[project.status])}
            >
              {project.status.replace("_", " ")}
            </Badge>
            {project.pending_checkpoint && (
              <Badge variant="outline" className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-700 dark:text-amber-300">
                checkpoint pending
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground text-xs">
            Stage {project.current_stage_index + 1}/{project.total_stages}
            {project.current_stage && ` · ${project.current_stage}`}
            {project.total_iterations > 0 && ` · ${project.total_iterations} iterations`}
          </p>
        </div>
        {expanded ? (
          <ChevronDownIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRightIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
        )}
      </button>
      {expanded && <ProjectDetail projectId={project.project_id} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function ExecutiveProjects() {
  const projectsQuery = useQuery({
    queryKey: ["executive", "projects"],
    queryFn: () => listProjects(),
    refetchInterval: 45_000, // Reduced from 15s: projects list is relatively static
  });

  const projects = projectsQuery.data?.projects ?? [];
  const activeProjects = projects.filter(
    (p) => p.status === "running" || p.status === "waiting_approval" || p.status === "paused",
  );
  const otherProjects = projects.filter(
    (p) => p.status !== "running" && p.status !== "waiting_approval" && p.status !== "paused",
  );

  return (
    <Card className="border-border/60 py-4">
      <CardHeader className="flex flex-row items-center justify-between px-4">
        <div>
          <CardTitle className="flex items-center gap-2 text-base">
            <FolderKanbanIcon className="size-4" />
            Projects
            {activeProjects.length > 0 && (
              <Badge variant="outline" className="rounded-full border-blue-500/30 bg-blue-500/10 px-2 text-blue-700 dark:text-blue-300">
                {activeProjects.length} active
              </Badge>
            )}
          </CardTitle>
          <CardDescription>
            Multi-stage orchestration projects managed by the Executive Agent.
          </CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void projectsQuery.refetch()}
          disabled={projectsQuery.isFetching}
        >
          {projectsQuery.isFetching ? (
            <Loader2Icon className="size-4 animate-spin" />
          ) : (
            <RefreshCwIcon className="size-4" />
          )}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3 px-4">
        {projectsQuery.isLoading && (
          <div className="text-muted-foreground rounded-xl border border-dashed p-4 text-center text-sm">
            Loading projects…
          </div>
        )}
        {!projectsQuery.isLoading && projects.length === 0 && (
          <div className="text-muted-foreground rounded-xl border border-dashed p-4 text-center text-sm">
            No projects yet. Ask the Executive Agent to create one.
          </div>
        )}
        {activeProjects.map((project) => (
          <ProjectRow key={project.project_id} project={project} />
        ))}
        {otherProjects.length > 0 && activeProjects.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ClockIcon className="size-3" />
            Past projects
          </div>
        )}
        {otherProjects.map((project) => (
          <ProjectRow key={project.project_id} project={project} />
        ))}
      </CardContent>
    </Card>
  );
}
