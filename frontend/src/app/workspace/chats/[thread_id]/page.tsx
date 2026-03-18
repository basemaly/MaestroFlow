"use client";

import { ClipboardCheckIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { type PromptInputMessage } from "@/components/ai-elements/prompt-input";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  ChatBox,
  useSpecificChatMode,
  useThreadChat,
} from "@/components/workspace/chats";
import { ContextDock } from "@/components/workspace/context-dock";
import { DeerIntroOverlay } from "@/components/workspace/deer-intro-overlay";
import { ExecutiveDrawerTrigger } from "@/components/workspace/executive-drawer";
import { ExternalServiceBanner } from "@/components/workspace/external-service-banner";
import { InputBox } from "@/components/workspace/input-box";
import { MessageList } from "@/components/workspace/messages";
import { ThreadContext } from "@/components/workspace/messages/context";
import { PlanReviewCard } from "@/components/workspace/plan-review-card";
import { ThreadTitle } from "@/components/workspace/thread-title";
import { TodoList } from "@/components/workspace/todo-list";
import { useI18n } from "@/core/i18n/hooks";
import { useNotification } from "@/core/notification/hooks";
import {
  answerPlanningQuestions,
  applyExecutiveSuggestions,
  approvePlanningReview,
  revisePlan,
  startFirstTurnReview,
} from "@/core/planning/api";
import type { FirstTurnReviewResponse } from "@/core/planning/types";
import { useLocalSettings } from "@/core/settings";
import { useThreadStream } from "@/core/threads/hooks";
import { textOfMessage } from "@/core/threads/utils";
import { env } from "@/env";
import { cn } from "@/lib/utils";

export default function ChatPage() {
  const { t } = useI18n();
  const [settings, setSettings] = useLocalSettings();
  const [isHydrated, setIsHydrated] = useState(false);
  const [submitWarning, setSubmitWarning] = useState<string | null>(null);
  const [planningReview, setPlanningReview] = useState<FirstTurnReviewResponse | null>(null);
  const [pendingMessage, setPendingMessage] = useState<PromptInputMessage | null>(null);
  const [planningBusy, setPlanningBusy] = useState(false);
  const [manualPlanReview, setManualPlanReview] = useState(false);
  const router = useRouter();

  const { threadId, isNewThread, setIsNewThread, isMock, isInvalidThreadRoute } =
    useThreadChat();
  useSpecificChatMode();

  const { showNotification } = useNotification();

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    if (!isInvalidThreadRoute) {
      return;
    }
    toast.error("That chat link is no longer valid. Starting a new thread instead.");
    router.replace("/workspace/chats/new");
  }, [isInvalidThreadRoute, router]);

  const [thread, sendMessage, serviceWarning, isRecursionError, continueResearch] = useThreadStream({
    threadId: isNewThread || isInvalidThreadRoute ? undefined : threadId,
    context: settings.context,
    isMock,
    onStart: () => {
      setIsNewThread(false);
      history.replaceState(null, "", `/workspace/chats/${threadId}`);
    },
    onFinish: (state) => {
      if (document.hidden || !document.hasFocus()) {
        let body = "Conversation finished";
        const lastMessage = state.messages.at(-1);
        if (lastMessage) {
          const textContent = textOfMessage(lastMessage);
          if (textContent) {
            body =
              textContent.length > 200
                ? textContent.substring(0, 200) + "..."
                : textContent;
          }
        }
        showNotification(state.title, { body });
      }
    },
  });

  const isFirstTurn = useMemo(() => {
    const visibleMessages = thread.messages.filter(
      (message) => message.type === "human" || message.type === "ai",
    );
    return isNewThread || visibleMessages.length === 0;
  }, [isNewThread, thread.messages]);

  const mergeContextPatch = useCallback(
    (patch: Record<string, unknown>) => {
      if (Object.keys(patch).length === 0) {
        return;
      }
      setSettings("context", patch);
    },
    [setSettings],
  );

  const executeReviewedRun = useCallback(
    async (decision: "approve" | "proceed_anyway") => {
      if (!planningReview || !pendingMessage) {
        return;
      }
      setPlanningBusy(true);
      try {
        const result = await approvePlanningReview({
          thread_id: planningReview.thread_id,
          decision,
        });
        mergeContextPatch(result.context_patch);
        await sendMessage(
          threadId,
          {
            ...pendingMessage,
            text: result.prompt,
          },
          result.context_patch,
        );
        setPlanningReview(null);
        setPendingMessage(null);
        setManualPlanReview(false);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setSubmitWarning(message);
        toast.error(message);
      } finally {
        setPlanningBusy(false);
      }
    },
    [mergeContextPatch, pendingMessage, planningReview, sendMessage, threadId],
  );

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      setSubmitWarning(null);
      if (planningReview) {
        toast.error("Finish the active plan review before sending another prompt.");
        return;
      }

      if (isFirstTurn || manualPlanReview) {
        setPlanningBusy(true);
        void startFirstTurnReview({
          thread_id: threadId,
          prompt: message.text,
          context: settings.context as Record<string, unknown>,
          force_review: manualPlanReview,
        })
          .then((review) => {
            if (
              review.review_required ||
              manualPlanReview ||
              review.suggestions.length > 0 ||
              review.questions.length > 0
            ) {
              setPlanningReview(review);
              setPendingMessage(message);
              return;
            }
            return sendMessage(threadId, message);
          })
          .catch((error: unknown) => {
            const errorMessage = error instanceof Error ? error.message : String(error);
            setSubmitWarning(errorMessage);
            toast.error(errorMessage);
          })
          .finally(() => {
            setPlanningBusy(false);
            setManualPlanReview(false);
          });
        return;
      }

      void sendMessage(threadId, message).catch((error: unknown) => {
        const errorMessage = error instanceof Error ? error.message : String(error);
        setSubmitWarning(errorMessage);
        toast.error(errorMessage);
      });
    },
    [isFirstTurn, manualPlanReview, planningReview, sendMessage, settings.context, threadId],
  );
  const handleStop = useCallback(async () => {
    await thread.stop();
  }, [thread]);

  if (!isHydrated) {
    return <div className="bg-background size-full" />;
  }

  return (
    <ThreadContext.Provider value={{ thread, isMock }}>
      <ChatBox threadId={threadId}>
        <div className="relative flex size-full min-h-0 justify-between">
          <header
            className={cn(
              "absolute top-0 right-0 left-0 z-30 flex h-12 shrink-0 items-center px-4 transition-colors duration-500",
              isNewThread
                ? "bg-gradient-to-b from-background/45 to-transparent backdrop-blur-[2px]"
                : "bg-background/80 shadow-xs backdrop-blur",
            )}
          >
            <div className="flex w-full items-center text-sm font-medium">
              <ThreadTitle threadId={threadId} thread={thread} />
            </div>
            <div className="flex items-center gap-1.5">
              <Button
                size="sm"
                variant={manualPlanReview ? "default" : "ghost"}
                onClick={() => {
                  if (!isFirstTurn) {
                    toast.error("Plan review can only be started before the first run in a thread.");
                    return;
                  }
                  setManualPlanReview((current) => !current);
                }}
              >
                <ClipboardCheckIcon className="size-4" />
                {manualPlanReview ? "Armed" : "Review Plan"}
              </Button>
              <ExecutiveDrawerTrigger isSidebarOpen={false} variant="header" />
            </div>
          </header>
          <main className="relative isolate flex min-h-0 max-w-full grow flex-col">
            <DeerIntroOverlay active={isNewThread} />
            <ExternalServiceBanner />
            <div className="px-4 pt-14 pb-2">
              <ContextDock
                knowledgeSource={
                  (settings.context.knowledge_source as "auto" | "calibre-library" | undefined) ??
                  "auto"
                }
                onKnowledgeSourceChange={(knowledge_source) =>
                  setSettings("context", { knowledge_source })
                }
                agentPreset={
                  typeof settings.context.agent_name === "string"
                    ? settings.context.agent_name
                    : undefined
                }
                onAgentPresetChange={(agent_name) =>
                  setSettings("context", { agent_name })
                }
                mode={settings.context.mode}
                disabled={env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"}
                includeArtifacts
                includeRevisionLab
              />
            </div>
            {planningReview && (
              <PlanReviewCard
                review={planningReview}
                busy={planningBusy}
                onApprove={() => void executeReviewedRun("approve")}
                onProceedAnyway={() => void executeReviewedRun("proceed_anyway")}
                onApplySuggestions={(suggestionIds) => {
                  setPlanningBusy(true);
                  void applyExecutiveSuggestions({
                    thread_id: planningReview.thread_id,
                    suggestion_ids: suggestionIds,
                  })
                    .then(setPlanningReview)
                    .catch((error) => {
                      toast.error(error instanceof Error ? error.message : String(error));
                    })
                    .finally(() => setPlanningBusy(false));
                }}
                onRevise={(payload) => {
                  setPlanningBusy(true);
                  void revisePlan({
                    thread_id: planningReview.thread_id,
                    goal_reframe: payload.goal_reframe,
                    edited_steps: payload.edited_steps,
                  })
                    .then(setPlanningReview)
                    .catch((error) => {
                      toast.error(error instanceof Error ? error.message : String(error));
                    })
                    .finally(() => setPlanningBusy(false));
                }}
                onAnswerQuestions={(answers) => {
                  setPlanningBusy(true);
                  void answerPlanningQuestions({
                    thread_id: planningReview.thread_id,
                    answers,
                  })
                    .then(setPlanningReview)
                    .catch((error) => {
                      toast.error(error instanceof Error ? error.message : String(error));
                    })
                    .finally(() => setPlanningBusy(false));
                }}
              />
            )}
            {(serviceWarning ?? submitWarning) && (
              <Alert className="mx-auto mt-2 mb-2 max-w-(--container-width-md) border-amber-500/30 bg-amber-500/8 text-amber-950 dark:text-amber-100">
                <AlertTitle>Chat service warning</AlertTitle>
                <AlertDescription>
                  {serviceWarning ?? submitWarning}
                  {isRecursionError && (
                    <button
                      onClick={() => void continueResearch()}
                      className="ml-3 inline-flex items-center rounded bg-amber-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-amber-700 focus:outline-none"
                    >
                      Continue
                    </button>
                  )}
                </AlertDescription>
              </Alert>
            )}
            <div className="flex size-full justify-center">
              <MessageList
                className={cn("size-full", !isNewThread && "pt-10")}
                threadId={threadId}
                thread={thread}
              />
            </div>
            <div className="absolute right-0 bottom-0 left-0 z-30 flex justify-center px-4">
              <div
                className={cn(
                  "relative w-full",
                  isNewThread && "-translate-y-[calc(50vh-96px)]",
                  isNewThread
                    ? "max-w-[60rem]"
                    : "max-w-(--container-width-md)",
                )}
              >
                <div className="absolute -top-4 right-0 left-0 z-0">
                  <div className="absolute right-0 bottom-0 left-0">
                    <TodoList
                      className="bg-background/5"
                      todos={thread.values.todos ?? []}
                      hidden={
                        !thread.values.todos || thread.values.todos.length === 0
                      }
                    />
                  </div>
                </div>
                <InputBox
                  className={cn(
                    "w-full -translate-y-4 transition-all duration-500",
                    isNewThread
                      ? "bg-background/6 backdrop-blur-sm"
                      : "bg-background/5",
                  )}
                  isNewThread={isNewThread}
                  threadId={threadId}
                  autoFocus={isNewThread}
                  status={thread.isLoading ? "streaming" : "ready"}
                  context={settings.context}
                  disabled={env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"}
                  extraHeader={undefined}
                  onContextChange={(context) => setSettings("context", context)}
                  onSubmit={handleSubmit}
                  onStop={handleStop}
                />
                {env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" && (
                  <div className="text-muted-foreground/67 w-full translate-y-12 text-center text-xs">
                    {t.common.notAvailableInDemoMode}
                  </div>
                )}
              </div>
            </div>
          </main>
        </div>
      </ChatBox>
    </ThreadContext.Provider>
  );
}
