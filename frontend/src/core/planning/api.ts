import { apiFetch } from "@/core/api/fetch";

import type {
  FirstTurnReviewResponse,
  PlanApprovalResult,
  PlanStep,
} from "./types";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Planning API failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function startFirstTurnReview(body: {
  thread_id: string;
  prompt: string;
  context: Record<string, unknown>;
  agent_name?: string;
  force_review?: boolean;
}): Promise<FirstTurnReviewResponse> {
  return api("/api/planning/first-turn-review", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function revisePlan(body: {
  thread_id: string;
  goal_reframe?: string;
  edited_steps?: PlanStep[];
}): Promise<FirstTurnReviewResponse> {
  return api("/api/planning/revise", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function answerPlanningQuestions(body: {
  thread_id: string;
  answers: Record<string, string>;
}): Promise<FirstTurnReviewResponse> {
  return api("/api/planning/answer-questions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function applyExecutiveSuggestions(body: {
  thread_id: string;
  suggestion_ids: string[];
}): Promise<FirstTurnReviewResponse> {
  return api("/api/planning/apply-executive-suggestions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function approvePlanningReview(body: {
  thread_id: string;
  decision: "approve" | "proceed_anyway";
}): Promise<PlanApprovalResult> {
  return api("/api/planning/approve", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
