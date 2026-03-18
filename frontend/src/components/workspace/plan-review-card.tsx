"use client";

import {
  BotIcon,
  ClipboardCheckIcon,
  CpuIcon,
  Edit3Icon,
  HelpCircleIcon,
  LayersIcon,
  SparklesIcon,
  WrenchIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type {
  ClarificationQuestion,
  ExecutiveSuggestion,
  FirstTurnReviewResponse,
  PlanStep,
} from "@/core/planning/types";
import { cn } from "@/lib/utils";

function badgeTone(severity: "low" | "medium" | "high") {
  if (severity === "high") return "border-red-500/40 bg-red-500/10 text-red-800 dark:text-red-200";
  if (severity === "medium") return "border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200";
  return "border-sky-500/40 bg-sky-500/10 text-sky-800 dark:text-sky-200";
}

function costBadge(level: string) {
  if (level === "high") return "text-red-600 dark:text-red-400";
  if (level === "medium") return "text-amber-600 dark:text-amber-400";
  return "text-emerald-600 dark:text-emerald-400";
}

export function PlanReviewCard({
  review,
  busy = false,
  onApprove,
  onProceedAnyway,
  onApplySuggestions,
  onRevise,
  onAnswerQuestions,
}: {
  review: FirstTurnReviewResponse;
  busy?: boolean;
  onApprove: () => void;
  onProceedAnyway: () => void;
  onApplySuggestions: (suggestionIds: string[]) => void;
  onRevise: (payload: { goal_reframe?: string; edited_steps?: PlanStep[] }) => void;
  onAnswerQuestions: (answers: Record<string, string>) => void;
}) {
  const [goalReframe, setGoalReframe] = useState("");
  const [steps, setSteps] = useState<PlanStep[]>(review.plan.steps);
  const [selectedSuggestionIds, setSelectedSuggestionIds] = useState<string[]>(
    review.suggestions.filter((item) => item.kind !== "warn_degraded_service").map((item) => item.suggestion_id),
  );
  const [answers, setAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    setSteps(review.plan.steps);
  }, [review.plan.steps]);

  useEffect(() => {
    setSelectedSuggestionIds(
      review.suggestions.filter((item) => item.kind !== "warn_degraded_service").map((item) => item.suggestion_id),
    );
  }, [review.suggestions]);

  const activeStepCount = useMemo(() => steps.filter((step) => step.enabled).length, [steps]);

  const toggleSuggestion = (suggestion: ExecutiveSuggestion) => {
    setSelectedSuggestionIds((current) =>
      current.includes(suggestion.suggestion_id)
        ? current.filter((id) => id !== suggestion.suggestion_id)
        : [...current, suggestion.suggestion_id],
    );
  };

  const updateStep = (stepId: string, patch: Partial<PlanStep>) => {
    setSteps((current) =>
      current.map((step) => (step.step_id === stepId ? { ...step, ...patch } : step)),
    );
  };

  const submitAnswers = () => {
    const cleaned = Object.fromEntries(
      Object.entries(answers).filter(([, value]) => value.trim().length > 0),
    );
    if (Object.keys(cleaned).length > 0) {
      onAnswerQuestions(cleaned);
    }
  };

  const audit = review.plan.prompt_audit;
  const rec = review.plan.recommendations;

  return (
    <div className="mx-auto mt-3 mb-3 w-full max-w-(--container-width-md) rounded-2xl border border-border/70 bg-background/92 shadow-sm backdrop-blur">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 border-b border-border/60 px-4 py-4">
        <div>
          <div className="text-foreground flex items-center gap-2 text-sm font-semibold">
            <ClipboardCheckIcon className="size-4" />
            Plan Review
          </div>
          <div className="text-muted-foreground mt-1 text-sm">{review.plan.summary}</div>
          <div className="text-muted-foreground mt-1 text-xs">
            {review.complexity.replaceAll("_", " ")} ·{" "}
            <span className={costBadge(review.plan.estimated_cost)}>{review.plan.estimated_cost} cost</span>
            {" · "}
            {review.plan.estimated_latency} latency
          </div>
        </div>
        <div className="text-muted-foreground text-xs">
          {activeStepCount} active step{activeStepCount === 1 ? "" : "s"}
        </div>
      </div>

      {/* Prompt audit — shown when LLM found issues or suggested a better prompt */}
      {audit && (
        <div className="border-b border-border/60 px-4 py-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
            <SparklesIcon className="size-3.5" />
            Prompt Audit
          </div>
          {audit.issues.length > 0 && (
            <ul className="text-muted-foreground mb-2 space-y-0.5 text-xs">
              {audit.issues.map((issue, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="mt-0.5 text-amber-500">·</span>
                  {issue}
                </li>
              ))}
            </ul>
          )}
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs">
            <div className="text-muted-foreground mb-1 font-medium">Suggested prompt</div>
            <div className="text-foreground/90 leading-relaxed">{audit.optimized_prompt}</div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="mt-2 text-xs"
            disabled={busy}
            onClick={() => {
              setGoalReframe(audit.optimized_prompt);
              onRevise({ goal_reframe: audit.optimized_prompt });
            }}
          >
            Use this prompt
          </Button>
        </div>
      )}

      {/* Recommendations — shown when LLM produced tool/model/mode suggestions */}
      {rec && (rec.mode || rec.model_name || rec.thinking_enabled || rec.tools.length > 0 || rec.subagent_count > 0) && (
        <div className="border-b border-border/60 px-4 py-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-foreground/60">
            <CpuIcon className="size-3.5" />
            Recommendations
          </div>
          <div className="flex flex-wrap gap-2">
            {rec.mode && (
              <div className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-background/60 px-2.5 py-1 text-xs">
                <LayersIcon className="size-3 text-sky-500" />
                <span className="text-muted-foreground">mode:</span>
                <span className="font-medium">{rec.mode}</span>
              </div>
            )}
            {rec.model_name && (
              <div className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-background/60 px-2.5 py-1 text-xs">
                <BotIcon className="size-3 text-violet-500" />
                <span className="text-muted-foreground">model:</span>
                <span className="font-medium">{rec.model_name}</span>
              </div>
            )}
            {rec.thinking_enabled && (
              <div className="flex items-center gap-1.5 rounded-lg border border-violet-500/30 bg-violet-500/8 px-2.5 py-1 text-xs text-violet-700 dark:text-violet-300">
                <CpuIcon className="size-3" />
                extended thinking
              </div>
            )}
            {rec.reasoning_effort && (
              <div className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-background/60 px-2.5 py-1 text-xs">
                <span className="text-muted-foreground">reasoning:</span>
                <span className="font-medium">{rec.reasoning_effort}</span>
              </div>
            )}
            {rec.subagent_count > 0 && (
              <div className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-background/60 px-2.5 py-1 text-xs">
                <LayersIcon className="size-3 text-emerald-500" />
                <span className="font-medium">{rec.subagent_count}</span>
                <span className="text-muted-foreground">sub-agent{rec.subagent_count > 1 ? "s" : ""}</span>
              </div>
            )}
            {rec.tools.map((tool) => (
              <div
                key={tool}
                className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-background/60 px-2.5 py-1 text-xs"
              >
                <WrenchIcon className="size-3 text-orange-500" />
                {tool}
              </div>
            ))}
          </div>
          {rec.rationale && (
            <p className="text-muted-foreground mt-2 text-xs leading-relaxed">{rec.rationale}</p>
          )}
        </div>
      )}

      <div className="grid gap-4 px-4 py-4 lg:grid-cols-[1.2fr_0.8fr]">
        {/* Left: plan steps + reframe */}
        <section className="space-y-3">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Edit3Icon className="size-4" />
              Execution Plan
            </div>
            <div className="space-y-2">
              {steps.map((step, index) => (
                <div key={step.step_id} className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={step.enabled}
                      onChange={(event) =>
                        updateStep(step.step_id, { enabled: event.target.checked })
                      }
                      className="mt-1 size-4 rounded border border-border"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="text-muted-foreground mb-1 text-[11px] uppercase tracking-wide">
                        Step {index + 1} · {step.kind}
                      </div>
                      <Input
                        value={step.title}
                        onChange={(event) => updateStep(step.step_id, { title: event.target.value })}
                        className="bg-background"
                      />
                      {step.details && (
                        <p className="text-muted-foreground mt-1.5 text-xs leading-relaxed">{step.details}</p>
                      )}
                      {step.sources.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {step.sources.map((src, si) => (
                            <span
                              key={si}
                              className="inline-flex items-center gap-1 rounded-md border border-border/50 bg-background/70 px-1.5 py-0.5 text-[11px] text-muted-foreground"
                            >
                              <WrenchIcon className="size-2.5" />
                              {src}
                            </span>
                          ))}
                        </div>
                      )}
                      {step.expected_output && (
                        <p className="text-muted-foreground mt-1.5 text-[11px]">
                          <span className="font-medium">Output:</span> {step.expected_output}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium">Reframe Goal</div>
            <Textarea
              value={goalReframe}
              onChange={(event) => setGoalReframe(event.target.value)}
              placeholder="Optional: tighten the objective, audience, constraints, or output format before execution."
              className="min-h-24"
            />
            <Button
              variant="outline"
              size="sm"
              disabled={busy || (!goalReframe.trim() && steps.every((step, index) => step.title === review.plan.steps[index]?.title && step.enabled === review.plan.steps[index]?.enabled))}
              onClick={() => onRevise({ goal_reframe: goalReframe.trim() || undefined, edited_steps: steps })}
            >
              Update Plan
            </Button>
          </div>
        </section>

        {/* Right: suggestions, questions, approve */}
        <section className="space-y-3">
          {review.suggestions.length > 0 && (
            <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                <SparklesIcon className="size-4" />
                Steering Options
              </div>
              <div className="space-y-2">
                {review.suggestions.map((suggestion) => (
                  <button
                    key={suggestion.suggestion_id}
                    type="button"
                    className={cn(
                      "w-full rounded-xl border px-3 py-2 text-left transition-colors",
                      badgeTone(suggestion.severity),
                      selectedSuggestionIds.includes(suggestion.suggestion_id) ? "ring-1 ring-foreground/20" : "opacity-85",
                    )}
                    onClick={() => toggleSuggestion(suggestion)}
                  >
                    <div className="text-sm font-medium">{suggestion.title}</div>
                    <div className="mt-1 text-xs opacity-90">{suggestion.summary}</div>
                  </button>
                ))}
              </div>
              <Button
                className="mt-3 w-full"
                variant="outline"
                size="sm"
                disabled={busy || selectedSuggestionIds.length === 0}
                onClick={() => onApplySuggestions(selectedSuggestionIds)}
              >
                Apply Selected
              </Button>
            </div>
          )}

          {review.questions.length > 0 && (
            <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                <HelpCircleIcon className="size-4" />
                Clarifying Questions
              </div>
              <div className="space-y-3">
                {review.questions.map((question: ClarificationQuestion) => (
                  <div key={question.question_id} className="space-y-1">
                    <div className="text-sm">{question.question}</div>
                    <div className="text-muted-foreground text-xs">{question.rationale}</div>
                    <Input
                      value={answers[question.question_id] ?? ""}
                      onChange={(event) =>
                        setAnswers((current) => ({
                          ...current,
                          [question.question_id]: event.target.value,
                        }))
                      }
                      placeholder={question.options[0] ?? "Your answer"}
                    />
                  </div>
                ))}
              </div>
              <Button className="mt-3 w-full" variant="outline" size="sm" disabled={busy} onClick={submitAnswers}>
                Regenerate with Answers
              </Button>
            </div>
          )}

          <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
            <div className="text-sm font-medium">Execution</div>
            <div className="text-muted-foreground mt-1 text-xs">
              Approve the plan and steering options, or run the original request directly.
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" disabled={busy} onClick={onApprove}>
                Approve Plan
              </Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={onProceedAnyway}>
                Proceed Anyway
              </Button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
