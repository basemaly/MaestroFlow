"use client";

import { BotIcon, PlusSquare } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import type { PromptInputMessage } from "@/components/ai-elements/prompt-input";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ArtifactTrigger } from "@/components/workspace/artifacts";
import { ChatBox, useThreadChat } from "@/components/workspace/chats";
import { DeerIntroOverlay } from "@/components/workspace/deer-intro-overlay";
import { DocEditDialog } from "@/components/workspace/doc-edit-dialog";
import { ExternalServiceBanner } from "@/components/workspace/external-service-banner";
import { InputBox } from "@/components/workspace/input-box";
import { MessageList } from "@/components/workspace/messages";
import { ThreadContext } from "@/components/workspace/messages/context";
import { SurfSenseActions } from "@/components/workspace/surfsense-actions";
import { ThreadTitle } from "@/components/workspace/thread-title";
import { TodoList } from "@/components/workspace/todo-list";
import { Tooltip } from "@/components/workspace/tooltip";
import { useAgent } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";
import { useNotification } from "@/core/notification/hooks";
import { useLocalSettings } from "@/core/settings";
import { useThreadStream } from "@/core/threads/hooks";
import { textOfMessage } from "@/core/threads/utils";
import { env } from "@/env";
import { cn } from "@/lib/utils";

export default function AgentChatPage() {
  const { t } = useI18n();
  const [settings, setSettings] = useLocalSettings();
  const [submitWarning, setSubmitWarning] = useState<string | null>(null);
  const router = useRouter();

  const { agent_name } = useParams<{
    agent_name: string;
  }>();

  const { agent } = useAgent(agent_name);

  const { threadId, isNewThread, setIsNewThread, isInvalidThreadRoute } =
    useThreadChat();

  useEffect(() => {
    if (!isInvalidThreadRoute) {
      return;
    }
    toast.error("That chat link is no longer valid. Starting a new thread instead.");
    router.replace(`/workspace/agents/${agent_name}/chats/new`);
  }, [agent_name, isInvalidThreadRoute, router]);

  const { showNotification } = useNotification();
  const [thread, sendMessage, serviceWarning] = useThreadStream({
    threadId: isNewThread || isInvalidThreadRoute ? undefined : threadId,
    context: { ...settings.context, agent_name: agent_name },
    onStart: () => {
      setIsNewThread(false);
      history.replaceState(
        null,
        "",
        `/workspace/agents/${agent_name}/chats/${threadId}`,
      );
    },
    onFinish: (state) => {
      if (document.hidden || !document.hasFocus()) {
        let body = "Conversation finished";
        const lastMessage = state.messages[state.messages.length - 1];
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

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      setSubmitWarning(null);
      void sendMessage(threadId, message, { agent_name }).catch(
        (error: unknown) => {
          const errorMessage =
            error instanceof Error ? error.message : String(error);
          setSubmitWarning(errorMessage);
          toast.error(errorMessage);
        },
      );
    },
    [sendMessage, threadId, agent_name],
  );

  const handleStop = useCallback(async () => {
    await thread.stop();
  }, [thread]);

  return (
    <ThreadContext.Provider value={{ thread }}>
      <ChatBox threadId={threadId}>
        <div className="relative flex size-full min-h-0 justify-between">
          <header
            className={cn(
              "absolute top-0 right-0 left-0 z-30 flex h-12 shrink-0 items-center gap-2 px-4 transition-colors duration-500",
              isNewThread
                ? "bg-gradient-to-b from-background/45 to-transparent backdrop-blur-[2px]"
                : "bg-background/80 shadow-xs backdrop-blur",
            )}
          >
            {/* Agent badge */}
            <div className="flex shrink-0 items-center gap-1.5 rounded-md border px-2 py-1">
              <BotIcon className="text-primary h-3.5 w-3.5" />
              <span className="text-xs font-medium">
                {agent?.name ?? agent_name}
              </span>
            </div>

            <div className="flex w-full items-center text-sm font-medium">
              <ThreadTitle threadId={threadId} thread={thread} />
            </div>
            <div className="mr-4 flex items-center gap-2">
              <SurfSenseActions />
              <DocEditDialog
                disabled={env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"}
                mode={settings.context.mode}
              />
              <Tooltip content={t.agents.newChat}>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    router.push(`/workspace/agents/${agent_name}/chats/new`);
                  }}
                >
                  <PlusSquare /> {t.agents.newChat}
                </Button>
              </Tooltip>
              <ArtifactTrigger />
            </div>
          </header>

          <main className="flex min-h-0 max-w-full grow flex-col">
            <DeerIntroOverlay active={isNewThread} />
            <ExternalServiceBanner />
            {(serviceWarning ?? submitWarning) && (
              <Alert className="mx-auto mt-2 mb-2 max-w-(--container-width-md) border-amber-500/30 bg-amber-500/8 text-amber-950 dark:text-amber-100">
                <AlertTitle>Chat service warning</AlertTitle>
                <AlertDescription>{serviceWarning ?? submitWarning}</AlertDescription>
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
                    ? "max-w-(--container-width-sm)"
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
