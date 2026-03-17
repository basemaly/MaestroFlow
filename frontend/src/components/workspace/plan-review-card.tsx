"use client";

import { ClipboardCheckIcon, Edit3Icon, HelpCircleIcon, SparklesIcon } from "lucide-react";
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

  return (
    <div className="mx-auto mt-3 mb-3 w-full max-w-(--container-width-md) rounded-2xl border border-border/70 bg-background/92 shadow-sm backdrop-blur">
      <div className="flex items-start justify-between gap-4 border-b border-border/60 px-4 py-4">
        <div>
          <div className="text-foreground flex items-center gap-2 text-sm font-semibold">
            <ClipboardCheckIcon className="size-4" />
            Plan Review
          </div>
          <div className="text-muted-foreground mt-1 text-sm">{review.plan.summary}</div>
          <div className="text-muted-foreground mt-1 text-xs">
            {review.complexity.replaceAll("_", " ")} · {review.plan.estimated_cost} cost · {review.plan.estimated_latency} latency
          </div>
        </div>
        <div className="text-muted-foreground text-xs">
          {activeStepCount} active step{activeStepCount === 1 ? "" : "s"}
        </div>
      </div>

      <div className="grid gap-4 px-4 py-4 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="space-y-3">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Edit3Icon className="size-4" />
              Draft Plan
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

        <section className="space-y-3">
          {review.suggestions.length > 0 && (
            <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                <SparklesIcon className="size-4" />
                Executive Suggestions
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
                Apply Executive Suggestions
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
              Approve the reviewed plan, or bypass it and run the original request directly.
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
