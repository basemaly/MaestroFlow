"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRightIcon,
  CheckCircle2Icon,
  FlaskConicalIcon,
  HourglassIcon,
  ImageIcon,
  PlayIcon,
  ShieldCheckIcon,
  SquareIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  approveAutoresearchExperiment,
  createPromptExperiment,
  createUiDesignExperiment,
  createWorkflowRouteExperiment,
  rejectAutoresearchExperiment,
  stopAutoresearchExperiment,
} from "@/core/autoresearch/api";
import { useAutoresearchExperiment, useAutoresearchExperiments, useAutoresearchRegistry } from "@/core/autoresearch/hooks";
import type {
  AutoresearchRegistryPayload,
  BenchmarkRunResult,
  ExperimentSummary,
  WorkflowTemplateSummary,
} from "@/core/autoresearch/types";

const STATUS_STYLES: Record<string, string> = {
  running: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
  awaiting_approval: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  promoted: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  evaluated: "bg-slate-500/10 text-slate-700 dark:text-slate-300",
  rejected: "bg-rose-500/10 text-rose-700 dark:text-rose-300",
  stopped: "bg-zinc-500/10 text-zinc-700 dark:text-zinc-300",
};

function statusTone(status: string) {
  return STATUS_STYLES[status] ?? "bg-zinc-500/10 text-zinc-700 dark:text-zinc-300";
}

function getCritiqueField(candidate: ExperimentSummary["domain"] extends never ? never : { metadata?: Record<string, unknown> }, field: string): string | null {
  const critique = candidate.metadata?.critique;
  if (!critique || typeof critique !== "object") {
    return null;
  }
  const value = (critique as Record<string, unknown>)[field];
  return typeof value === "string" ? value : null;
}

function getWorkflowTemplateBadge(template: WorkflowTemplateSummary) {
  return template.has_promoted_variant ? `Champion v${template.champion_version}` : "Baseline only";
}

function getWorkflowCandidateMetric(candidate: { metadata?: Record<string, unknown> }, key: string): number | null {
  const metadata = candidate.metadata;
  if (!metadata) {
    return null;
  }
  if (typeof metadata[key] === "number") {
    return metadata[key];
  }
  const baselineComparison = metadata.baseline_comparison;
  if (baselineComparison && typeof baselineComparison === "object") {
    const value = (baselineComparison as Record<string, unknown>)[key];
    return typeof value === "number" ? value : null;
  }
  const scoreBreakdown = metadata.score_breakdown;
  if (scoreBreakdown && typeof scoreBreakdown === "object") {
    const value = (scoreBreakdown as Record<string, unknown>)[key];
    return typeof value === "number" ? value : null;
  }
  return null;
}

function getWorkflowQualityPassed(candidate: { metadata?: Record<string, unknown> }): boolean | null {
  const qualityGate = candidate.metadata?.quality_gate;
  if (!qualityGate || typeof qualityGate !== "object") {
    return null;
  }
  const passed = (qualityGate as Record<string, unknown>).passed;
  return typeof passed === "boolean" ? passed : null;
}

function getBenchmarkResults(candidate: { metadata?: Record<string, unknown> }): BenchmarkRunResult[] {
  const raw = candidate.metadata?.benchmark_results;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.filter((item): item is BenchmarkRunResult => !!item && typeof item === "object" && "case_id" in item);
}

export function AutoresearchPageClient({
  registry,
  experiments,
}: {
  registry: AutoresearchRegistryPayload;
  experiments: ExperimentSummary[];
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [designTitle, setDesignTitle] = useState("Pricing card optimization");
  const [promptMutationCount, setPromptMutationCount] = useState("3");
  const [promptBenchmarkLimit, setPromptBenchmarkLimit] = useState("3");
  const [selectedWorkflowTemplateId, setSelectedWorkflowTemplateId] = useState(
    registry.workflow_templates?.[0]?.template_id ?? "research_report",
  );
  const [workflowMutationCount, setWorkflowMutationCount] = useState("3");
  const [designPrompt, setDesignPrompt] = useState(
    "Refine this pricing card so the typography hierarchy, spacing rhythm, CTA emphasis, and visual polish feel intentional and premium.",
  );
  const [designCode, setDesignCode] = useState(
    `<section class="mx-auto max-w-md rounded-3xl border border-slate-200 bg-white p-6">
  <div class="text-sm font-medium uppercase tracking-[0.2em] text-emerald-600">Pro plan</div>
  <h2 class="mt-3 text-3xl font-semibold text-slate-900">$29<span class="text-base font-medium text-slate-500">/mo</span></h2>
  <p class="mt-3 text-sm text-slate-600">Advanced research workflows, premium prompts, and collaborative memory.</p>
  <ul class="mt-5 space-y-2 text-sm text-slate-700">
    <li>Unlimited agent presets</li>
    <li>Priority executive workflows</li>
    <li>Knowledge integrations included</li>
  </ul>
  <button class="mt-6 w-full rounded-xl bg-emerald-600 px-4 py-3 text-sm font-medium text-white">Start trial</button>
</section>`,
  );
  const { data: registryData } = useAutoresearchRegistry(registry);
  const { data: experimentsData = [] } = useAutoresearchExperiments(experiments);
  const selectedExperimentId = searchParams.get("experiment") ?? experimentsData[0]?.experiment_id;
  const { data: selectedExperiment, isLoading: detailLoading } = useAutoresearchExperiment(selectedExperimentId);
  const promptMutationCountValue = Math.max(1, Math.min(5, Number.parseInt(promptMutationCount, 10) || 3));
  const promptBenchmarkLimitValue = Math.max(1, Math.min(10, Number.parseInt(promptBenchmarkLimit, 10) || 3));

  const createMutation = useMutation({
    mutationFn: (role: string) =>
      createPromptExperiment({
        role,
        title: `${role} prompt experiment`,
        max_mutations: promptMutationCountValue,
        benchmark_limit: promptBenchmarkLimitValue,
      }),
    onSuccess: (result) => {
      toast.success("Prompt experiment created");
      void queryClient.invalidateQueries({ queryKey: ["autoresearch", "experiments"] });
      router.push(`/workspace/autoresearch?experiment=${encodeURIComponent(result.experiment.experiment_id)}`);
      router.refresh();
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
  });

  const createDesignMutation = useMutation({
    mutationFn: () =>
      createUiDesignExperiment({
        title: designTitle,
        prompt: designPrompt,
        component_code: designCode,
        max_iterations: 3,
      }),
    onSuccess: (result) => {
      toast.success("Design optimization created");
      void queryClient.invalidateQueries({ queryKey: ["autoresearch"] });
      router.push(`/workspace/autoresearch?experiment=${encodeURIComponent(result.experiment.experiment_id)}`);
      router.refresh();
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
  });

  const createWorkflowMutation = useMutation({
    mutationFn: () =>
      createWorkflowRouteExperiment({
        template_id: selectedWorkflowTemplateId,
        title:
          registry.workflow_templates?.find((template) => template.template_id === selectedWorkflowTemplateId)?.title ??
          "Workflow route optimization",
        max_mutations: Number.parseInt(workflowMutationCount, 10) || 3,
      }),
    onSuccess: (result) => {
      toast.success("Workflow optimization created");
      void queryClient.invalidateQueries({ queryKey: ["autoresearch"] });
      router.push(`/workspace/autoresearch?experiment=${encodeURIComponent(result.experiment.experiment_id)}`);
      router.refresh();
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
  });

  const approveMutation = useMutation({
    mutationFn: (experimentId: string) => approveAutoresearchExperiment(experimentId),
    onSuccess: (_, experimentId) => {
      toast.success("Experiment promoted");
      void queryClient.invalidateQueries({ queryKey: ["autoresearch"] });
      router.replace(`/workspace/autoresearch?experiment=${encodeURIComponent(experimentId)}`);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
  });

  const rejectMutation = useMutation({
    mutationFn: (experimentId: string) => rejectAutoresearchExperiment(experimentId, "Rejected from lab review"),
    onSuccess: (_, experimentId) => {
      toast.success("Experiment rejected");
      void queryClient.invalidateQueries({ queryKey: ["autoresearch"] });
      router.replace(`/workspace/autoresearch?experiment=${encodeURIComponent(experimentId)}`);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
  });

  const stopMutation = useMutation({
    mutationFn: (experimentId: string) => stopAutoresearchExperiment(experimentId, "Stopped from lab console"),
    onSuccess: (_, experimentId) => {
      toast.success("Experiment stopped");
      void queryClient.invalidateQueries({ queryKey: ["autoresearch"] });
      router.replace(`/workspace/autoresearch?experiment=${encodeURIComponent(experimentId)}`);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
  });

  const awaitingApproval = experimentsData.filter((item) => item.promotion_status === "awaiting_approval");
  const runningExperiments = experimentsData.filter((item) => item.status === "running");
  const registryConfig = registryData ?? registry;
  const workflowTemplates = registryConfig.workflow_templates ?? [];
  const manualStartRequired = registryConfig.manual_start_required ?? true;
  const approvalRequired = registryConfig.approval_required ?? true;
  const schedulerEnabled = registryConfig.scheduler_enabled ?? false;
  const selectedWorkflowTemplate =
    workflowTemplates.find((template) => template.template_id === selectedWorkflowTemplateId) ?? workflowTemplates[0];

  return (
    <div className="mx-auto grid w-full max-w-7xl gap-6 xl:grid-cols-[0.95fr_1.35fr]">
      <aside className="space-y-4">
        <Card className="rounded-3xl border-border/60 bg-card/70 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FlaskConicalIcon className="h-4 w-4 text-emerald-500" />
              Manual prompt lab
            </CardTitle>
            <CardDescription>
              Autoresearcher is opt-in only. Nothing starts on page load, on deploy, or through background scheduling unless you explicitly launch it.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-border/60 bg-background/70 p-3">
                <div className="text-muted-foreground text-[11px] uppercase tracking-wide">Mutation count</div>
                <input
                  className="border-input bg-background mt-2 w-full rounded-md border px-3 py-2 text-sm"
                  value={promptMutationCount}
                  onChange={(event) => setPromptMutationCount(event.target.value)}
                  inputMode="numeric"
                  placeholder="3"
                />
              </div>
              <div className="rounded-2xl border border-border/60 bg-background/70 p-3">
                <div className="text-muted-foreground text-[11px] uppercase tracking-wide">Benchmark subset</div>
                <input
                  className="border-input bg-background mt-2 w-full rounded-md border px-3 py-2 text-sm"
                  value={promptBenchmarkLimit}
                  onChange={(event) => setPromptBenchmarkLimit(event.target.value)}
                  inputMode="numeric"
                  placeholder="3"
                />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-border/60 bg-background/70 p-3">
                <div className="text-muted-foreground text-[11px] uppercase tracking-wide">Start policy</div>
                <div className="mt-1 text-sm font-medium">
                  {manualStartRequired ? "Manual only" : "Automatic runs enabled"}
                </div>
              </div>
              <div className="rounded-2xl border border-border/60 bg-background/70 p-3">
                <div className="text-muted-foreground text-[11px] uppercase tracking-wide">Promotion</div>
                <div className="mt-1 text-sm font-medium">
                  {approvalRequired ? "Executive approval" : "Direct promotion"}
                </div>
              </div>
              <div className="rounded-2xl border border-border/60 bg-background/70 p-3">
                <div className="text-muted-foreground text-[11px] uppercase tracking-wide">Scheduler</div>
                <div className="mt-1 text-sm font-medium">
                  {schedulerEnabled ? "Enabled" : "Disabled"}
                </div>
              </div>
            </div>
            {registryConfig.champions.map((champion) => (
              <div key={champion.role} className="rounded-2xl border border-border/60 bg-background/70 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium">{champion.role}</div>
                    <div className="text-muted-foreground mt-1 text-xs">
                      Champion v{champion.version} · promoted by {champion.promoted_by}
                    </div>
                    <div className="text-muted-foreground mt-1 text-[11px]">
                      Start with {promptMutationCountValue} mutations across {promptBenchmarkLimitValue} benchmark case
                      {promptBenchmarkLimitValue === 1 ? "" : "s"}.
                    </div>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => createMutation.mutate(champion.role)}
                    disabled={createMutation.isPending}
                  >
                    <PlayIcon className="mr-1.5 h-3.5 w-3.5" />
                    Start
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="rounded-3xl border-border/60 bg-card/70 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ImageIcon className="h-4 w-4 text-sky-500" />
              Workflow routing optimization
            </CardTitle>
            <CardDescription>
              Run a bounded DAG experiment against a built-in workflow template. The lab benchmarks baseline routing, mutates models and edges, then
              stops at Executive review instead of self-promoting.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
              <select
                className="border-input bg-background/70 w-full rounded-md border px-3 py-2 text-sm"
                value={selectedWorkflowTemplateId}
                onChange={(event) => setSelectedWorkflowTemplateId(event.target.value)}
              >
                {workflowTemplates.map((template) => (
                  <option key={template.template_id} value={template.template_id}>
                    {template.title}
                  </option>
                ))}
              </select>
              <input
                className="border-input bg-background/70 w-full rounded-md border px-3 py-2 text-sm"
                value={workflowMutationCount}
                onChange={(event) => setWorkflowMutationCount(event.target.value)}
                inputMode="numeric"
                placeholder="Mutations"
              />
            </div>
            {selectedWorkflowTemplate ? (
              <div className="rounded-2xl border border-border/60 bg-background/70 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-sm font-medium">{selectedWorkflowTemplate.title}</div>
                  <Badge variant="outline">{getWorkflowTemplateBadge(selectedWorkflowTemplate)}</Badge>
                  <Badge variant="outline">{selectedWorkflowTemplate.node_count} nodes</Badge>
                </div>
                <div className="text-muted-foreground mt-2 text-sm">{selectedWorkflowTemplate.description}</div>
                <div className="text-muted-foreground mt-2 text-xs">
                  Objective: {selectedWorkflowTemplate.objective}
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground rounded-2xl border border-dashed p-4 text-sm">
                No workflow templates are registered yet.
              </div>
            )}
            <Button
              className="w-full"
              onClick={() => createWorkflowMutation.mutate()}
              disabled={createWorkflowMutation.isPending || !selectedWorkflowTemplateId}
            >
              <PlayIcon className="mr-1.5 h-3.5 w-3.5" />
              Start workflow optimization
            </Button>
          </CardContent>
        </Card>

        <Card className="rounded-3xl border-border/60 bg-card/70 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ImageIcon className="h-4 w-4 text-sky-500" />
              Design optimization
            </CardTitle>
            <CardDescription>
              Start an explicit <code>ui_design</code> experiment. The lab renders the component, critiques it, mutates it up to three times, and keeps the best candidate.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <input
              className="border-input bg-background/70 w-full rounded-md border px-3 py-2 text-sm"
              value={designTitle}
              onChange={(event) => setDesignTitle(event.target.value)}
              placeholder="Experiment title"
            />
            <Textarea
              value={designPrompt}
              onChange={(event) => setDesignPrompt(event.target.value)}
              className="min-h-24 bg-background/70"
              placeholder="Design goal"
            />
            <Textarea
              value={designCode}
              onChange={(event) => setDesignCode(event.target.value)}
              className="min-h-56 bg-background/70 font-mono text-xs"
              placeholder="Paste HTML or a self-contained component snippet"
            />
            <Button
              className="w-full"
              onClick={() => createDesignMutation.mutate()}
              disabled={createDesignMutation.isPending || !designPrompt.trim() || !designCode.trim()}
            >
              <PlayIcon className="mr-1.5 h-3.5 w-3.5" />
              Start design optimization
            </Button>
          </CardContent>
        </Card>

        <Card className="rounded-3xl border-border/60 bg-card/70 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Flow</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex items-start gap-2 text-muted-foreground">
              <CheckCircle2Icon className="mt-0.5 h-4 w-4 text-emerald-500" />
              <span>Autoresearcher owns experiments, benchmarks, and candidate scoring.</span>
            </div>
            <div className="flex items-start gap-2 text-muted-foreground">
              <HourglassIcon className="mt-0.5 h-4 w-4 text-amber-500" />
              <span>Anything strong enough moves to <code>awaiting_approval</code> and stops there.</span>
            </div>
            <div className="flex items-start gap-2 text-muted-foreground">
              <ShieldCheckIcon className="mt-0.5 h-4 w-4 text-sky-500" />
              <span>Executive stays the control plane for approve, reject, rollback, and stop.</span>
            </div>
            <Button asChild variant="outline" size="sm" className="mt-3 w-full">
              <Link href="/workspace/executive">
                Open Executive
                <ArrowRightIcon className="ml-1.5 h-3.5 w-3.5" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </aside>

      <section className="space-y-4">
        <Card className="rounded-3xl border-border/60 bg-card/70 shadow-sm">
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle className="text-base">Recent experiments</CardTitle>
                <CardDescription>
                  Prompt experiments share one registry and approval path. This keeps the lab logic in one place instead of duplicating it across Executive, agents, and runtime config.
                </CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge className="bg-amber-500/10 text-amber-700 dark:text-amber-300">
                  {awaitingApproval.length} awaiting approval
                </Badge>
                <Badge variant="outline">{runningExperiments.length} running</Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {experimentsData.length === 0 ? (
              <div className="text-muted-foreground rounded-2xl border border-dashed p-5 text-sm">
                No experiments yet. Start one explicitly from the left.
              </div>
            ) : (
              experimentsData.map((experiment) => (
                <button
                  key={experiment.experiment_id}
                  type="button"
                  onClick={() => router.replace(`/workspace/autoresearch?experiment=${encodeURIComponent(experiment.experiment_id)}`)}
                  className={`block w-full rounded-2xl border bg-background/70 p-4 text-left transition-colors ${
                    selectedExperimentId === experiment.experiment_id
                      ? "border-emerald-500/40 ring-1 ring-emerald-500/20"
                      : "border-border/60 hover:border-border"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-sm font-medium">{experiment.title}</div>
                        <Badge className={statusTone(experiment.status)}>{experiment.status}</Badge>
                        <Badge variant="outline">{experiment.role}</Badge>
                      </div>
                      <div className="text-muted-foreground text-xs">
                        Champion v{experiment.champion_version} · {experiment.candidate_count} candidates
                        {typeof experiment.top_score === "number" ? ` · top score ${experiment.top_score.toFixed(2)}` : ""}
                      </div>
                    </div>
                    {experiment.promotion_status === "awaiting_approval" ? (
                      <Badge className="bg-amber-500/10 text-amber-700 dark:text-amber-300">Executive review</Badge>
                    ) : null}
                  </div>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="rounded-3xl border-border/60 bg-card/70 shadow-sm">
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base">Experiment detail</CardTitle>
                <CardDescription>
                  Benchmarks and candidate variants stay visible in the lab. Promotion actions stay explicit and reversible.
                </CardDescription>
              </div>
              {selectedExperiment?.experiment ? (
                <div className="flex flex-wrap gap-2">
                  {selectedExperiment.experiment.promotion_status === "awaiting_approval" ? (
                    <>
                      <Button
                        size="sm"
                        onClick={() => approveMutation.mutate(selectedExperiment.experiment.experiment_id)}
                        disabled={approveMutation.isPending}
                      >
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => rejectMutation.mutate(selectedExperiment.experiment.experiment_id)}
                        disabled={rejectMutation.isPending}
                      >
                        Reject
                      </Button>
                    </>
                  ) : null}
                  {selectedExperiment.experiment.status === "running" ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => stopMutation.mutate(selectedExperiment.experiment.experiment_id)}
                      disabled={stopMutation.isPending}
                    >
                      <SquareIcon className="mr-1.5 h-3.5 w-3.5" />
                      Stop
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {!selectedExperimentId ? (
              <div className="text-muted-foreground rounded-2xl border border-dashed p-5 text-sm">
                Select an experiment to inspect candidates and benchmark coverage.
              </div>
            ) : detailLoading ? (
              <div className="text-muted-foreground rounded-2xl border border-dashed p-5 text-sm">
                Loading experiment detail…
              </div>
            ) : selectedExperiment ? (
              <>
                <div className="grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
                  <div className="rounded-2xl border border-border/60 bg-background/70 p-4">
                    <div className="mb-2 text-sm font-medium">Candidates</div>
                    <div className="space-y-3">
                      {selectedExperiment.candidates.map((candidate) => (
                        <div key={candidate.candidate_id} className="rounded-2xl border border-border/60 p-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline">{candidate.source}</Badge>
                            {candidate.score ? (
                              <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
                                Score {candidate.score.composite.toFixed(2)}
                              </Badge>
                            ) : (
                              <Badge className="bg-zinc-500/10 text-zinc-700 dark:text-zinc-300">Unscored</Badge>
                            )}
                            {candidate.promoted_at ? (
                              <Badge className="bg-sky-500/10 text-sky-700 dark:text-sky-300">Promoted</Badge>
                            ) : null}
                          </div>
                          {candidate.score ? (
                            <div className="text-muted-foreground mt-2 text-xs">
                              Correctness {candidate.score.correctness.toFixed(2)} · Efficiency {candidate.score.efficiency.toFixed(2)} · Speed{" "}
                              {candidate.score.speed.toFixed(2)}
                            </div>
                          ) : (
                            <div className="text-muted-foreground mt-2 text-xs">
                              Candidate created and ready for scoring. No benchmark score has been submitted yet.
                            </div>
                          )}
                          {selectedExperiment.experiment.domain === "workflow_route" ? (
                            <div className="mt-3 space-y-2 rounded-2xl border border-border/60 bg-background/70 p-3 text-xs text-muted-foreground">
                              <div>
                                Fitness {getWorkflowCandidateMetric(candidate, "fitness")?.toFixed(2) ?? "0.00"} · Latency ratio{" "}
                                {getWorkflowCandidateMetric(candidate, "latency_ratio")?.toFixed(2) ?? "1.00"} · Cost ratio{" "}
                                {getWorkflowCandidateMetric(candidate, "cost_ratio")?.toFixed(2) ?? "1.00"}
                              </div>
                              <div>
                                Quality gate{" "}
                                {getWorkflowQualityPassed(candidate) === null
                                  ? "unknown"
                                  : getWorkflowQualityPassed(candidate)
                                    ? "passed"
                                    : "failed"}
                              </div>
                              {Array.isArray(candidate.metadata?.mutations) && candidate.metadata?.mutations.length > 0 ? (
                                <div>
                                  Mutations:{" "}
                                  {(candidate.metadata.mutations as Array<Record<string, unknown>>)
                                    .map((mutation) =>
                                      typeof mutation.description === "string" ? mutation.description : "Unnamed mutation",
                                    )
                                    .join(" · ")}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                          {selectedExperiment.experiment.domain === "subagent_prompt" ? (
                            <div className="mt-3 space-y-2 rounded-2xl border border-border/60 bg-background/70 p-3 text-xs text-muted-foreground">
                              <div>
                                Strategy{" "}
                                {typeof candidate.metadata?.mutation_strategy === "string"
                                  ? candidate.metadata.mutation_strategy
                                  : candidate.source}
                              </div>
                              {typeof candidate.metadata?.benchmark_feedback === "string" ? (
                                <div className="line-clamp-5 whitespace-pre-wrap">
                                  {candidate.metadata.benchmark_feedback}
                                </div>
                              ) : null}
                              {getBenchmarkResults(candidate).length > 0 ? (
                                <div className="space-y-2">
                                  {getBenchmarkResults(candidate).map((result) => (
                                    <div key={result.case_id} className="rounded-xl border border-border/60 px-3 py-2">
                                      <div className="font-medium">{result.case_id}</div>
                                      <div>
                                        Correctness {result.correctness.toFixed(2)} · Efficiency {result.efficiency.toFixed(2)} · Speed{" "}
                                        {result.speed.toFixed(2)} · Composite {result.composite.toFixed(2)}
                                      </div>
                                      <div>
                                        {result.elapsed_seconds.toFixed(2)}s · ~{result.estimated_tokens} tokens
                                      </div>
                                      {result.notes ? <div>{result.notes}</div> : null}
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                          {typeof candidate.metadata?.visual_score === "number" ? (
                            <div className="text-muted-foreground mt-2 text-xs">
                              Visual score {candidate.metadata.visual_score.toFixed(2)} / 10 · Critic mode{" "}
                              {getCritiqueField(candidate, "critic_mode") ?? "unknown"}
                            </div>
                          ) : null}
                          {typeof candidate.metadata?.screenshot_url === "string" ? (
                            <div className="mt-3 overflow-hidden rounded-2xl border border-border/60 bg-white">
                              <img
                                src={candidate.metadata.screenshot_url}
                                alt={`${candidate.source} preview`}
                                className="h-auto w-full object-cover"
                              />
                            </div>
                          ) : null}
                          {candidate.metadata?.critique && typeof candidate.metadata.critique === "object" ? (
                            <div className="mt-3 rounded-2xl border border-border/60 bg-background/70 p-3">
                              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Critique</div>
                              <div className="mt-1 text-sm">
                                {getCritiqueField(candidate, "summary") ?? "No summary"}
                              </div>
                            </div>
                          ) : null}
                          {selectedExperiment.experiment.domain === "workflow_route" &&
                          candidate.metadata?.telemetry &&
                          typeof candidate.metadata.telemetry === "object" ? (
                            <div className="mt-3 rounded-2xl border border-border/60 bg-background/70 p-3">
                              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Telemetry</div>
                              <div className="mt-2 text-xs text-muted-foreground">
                                Wall time{" "}
                                {(() => {
                                  const telemetry = candidate.metadata?.telemetry as Record<string, unknown>;
                                  return typeof telemetry.wall_time_ms === "number"
                                    ? `${(telemetry.wall_time_ms / 1000).toFixed(2)}s`
                                    : "n/a";
                                })()}{" "}
                                · Cost $
                                {(() => {
                                  const telemetry = candidate.metadata?.telemetry as Record<string, unknown>;
                                  return typeof telemetry.total_cost_usd === "number"
                                    ? telemetry.total_cost_usd.toFixed(4)
                                    : "0.0000";
                                })()}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/70 p-4">
                    <div className="mb-2 text-sm font-medium">Benchmarks</div>
                    <div className="space-y-3">
                      {selectedExperiment.benchmarks.map((benchmark) => (
                        <div key={benchmark.case_id} className="rounded-2xl border border-border/60 p-3">
                          <div className="text-sm font-medium">{benchmark.title}</div>
                          <div className="text-muted-foreground mt-1 text-xs">{benchmark.prompt}</div>
                          <div className="text-muted-foreground mt-1 text-xs">{benchmark.validation_hint}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="text-muted-foreground rounded-2xl border border-border/60 bg-background/60 p-4 text-sm">
                  Front-end flow: start and inspect here. Back-end flow: registry and scoring live in the Autoresearch service. Control-plane flow:
                  approvals and rollbacks stay in Executive.
                </div>
              </>
            ) : (
              <div className="text-muted-foreground rounded-2xl border border-dashed p-5 text-sm">
                This experiment could not be loaded.
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
