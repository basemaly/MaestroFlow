import type { BaseStream } from "@langchain/langgraph-sdk/react";
import { useEffect, useRef } from "react";

import {
  Conversation,
  ConversationContent,
} from "@/components/ai-elements/conversation";
import { getBackendBaseURL } from "@/core/config";
import { useI18n } from "@/core/i18n/hooks";
import {
  extractContentFromMessage,
  extractPresentFilesFromMessage,
  extractTextFromMessage,
  groupMessages,
  hasContent,
  hasPresentFiles,
  hasReasoning,
} from "@/core/messages/utils";
import { useRehypeSplitWordsIntoSpans } from "@/core/rehype";
import type { Subtask } from "@/core/tasks";
import { parseTaskToolResult } from "@/core/tasks";
import { useUpdateSubtask } from "@/core/tasks/context";
import type { AgentThreadState } from "@/core/threads";
import { cn } from "@/lib/utils";

import { ArtifactFileList } from "../artifacts/artifact-file-list";
import { StreamingIndicator } from "../streaming-indicator";

import { MarkdownContent } from "./markdown-content";
import { MessageGroup } from "./message-group";
import { MessageListItem } from "./message-list-item";
import { MessageListSkeleton } from "./skeleton";
import { SubtaskCard } from "./subtask-card";

function isTaskQualityCandidate(value: unknown): value is NonNullable<Subtask["quality"]> {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.task_id === "string" &&
    typeof candidate.subagent_type === "string" &&
    typeof candidate.schema === "string" &&
    typeof candidate.composite === "number" &&
    typeof candidate.word_count === "number" &&
    Array.isArray(candidate.quality_warnings)
  );
}

export function MessageList({
  className,
  threadId,
  thread,
  paddingBottom = 160,
}: {
  className?: string;
  threadId: string;
  thread: BaseStream<AgentThreadState>;
  paddingBottom?: number;
}) {
  const { t } = useI18n();
  const rehypePlugins = useRehypeSplitWordsIntoSpans(thread.isLoading);
  const updateSubtask = useUpdateSubtask();
  const messages = thread.messages;
  // Track which threads we've already fetched quality scores for to avoid redundant requests.
  const fetchedThreadsRef = useRef(new Set<string>());

  useEffect(() => {
    if (fetchedThreadsRef.current.has(threadId)) {
      return;
    }

    const taskIds = new Set<string>();
    for (const message of messages) {
      if (message.type !== "ai") {
        continue;
      }
      for (const toolCall of message.tool_calls ?? []) {
        if (toolCall.name === "task" && toolCall.id) {
          taskIds.add(toolCall.id);
        }
      }
    }
    if (taskIds.size === 0) {
      return;
    }

    fetchedThreadsRef.current.add(threadId);
    const controller = new AbortController();
    fetch(`${getBackendBaseURL()}/api/threads/${threadId}/quality/`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          return { scores: [] as Array<Record<string, unknown>> };
        }
        return (await response.json()) as {
          scores?: Array<Record<string, unknown>>;
        };
      })
      .then((payload) => {
        for (const score of payload.scores ?? []) {
          if (!isTaskQualityCandidate(score)) {
            continue;
          }
          if (!taskIds.has(score.task_id)) {
            continue;
          }
          updateSubtask({
            id: score.task_id,
            quality: score,
          });
        }
      })
      .catch(() => undefined);

    return () => controller.abort();
  }, [messages, threadId, updateSubtask]);

  if (thread.isThreadLoading && messages.length === 0) {
    return <MessageListSkeleton />;
  }
  return (
    <Conversation
      className={cn("flex size-full flex-col justify-center", className)}
    >
      <ConversationContent className="mx-auto w-full max-w-(--container-width-md) gap-8 pt-12">
        {groupMessages(messages, (group) => {
          if (group.type === "human" || group.type === "assistant") {
            return group.messages.map((msg) => {
              return (
                <MessageListItem
                  key={`${group.id}/${msg.id}`}
                  message={msg}
                  isLoading={thread.isLoading}
                />
              );
            });
          } else if (group.type === "assistant:clarification") {
            const message = group.messages[0];
            if (message && hasContent(message)) {
              return (
                <MarkdownContent
                  key={group.id}
                  content={extractContentFromMessage(message)}
                  isLoading={thread.isLoading}
                  rehypePlugins={rehypePlugins}
                />
              );
            }
            return null;
          } else if (group.type === "assistant:present-files") {
            const files: string[] = [];
            for (const message of group.messages) {
              if (hasPresentFiles(message)) {
                const presentFiles = extractPresentFilesFromMessage(message);
                files.push(...presentFiles);
              }
            }
            return (
              <div className="w-full" key={group.id}>
                {group.messages[0] && hasContent(group.messages[0]) && (
                  <MarkdownContent
                    content={extractContentFromMessage(group.messages[0])}
                    isLoading={thread.isLoading}
                    rehypePlugins={rehypePlugins}
                    className="mb-4"
                  />
                )}
                <ArtifactFileList files={files} threadId={threadId} />
              </div>
            );
          } else if (group.type === "assistant:subagent") {
            const tasks = new Set<Subtask>();
            for (const message of group.messages) {
              if (message.type === "ai") {
                for (const toolCall of message.tool_calls ?? []) {
                  if (toolCall.name === "task") {
                    const task: Subtask = {
                      id: toolCall.id!,
                      subagent_type: toolCall.args.subagent_type,
                      description: toolCall.args.description,
                      prompt: toolCall.args.prompt,
                      status: "in_progress",
                    };
                    updateSubtask(task);
                    tasks.add(task);
                  }
                }
              } else if (message.type === "tool") {
                const taskId = message.tool_call_id;
                if (taskId) {
                  const result = extractTextFromMessage(message);
                  const parsed = parseTaskToolResult(result);
                  if (parsed?.status === "completed") {
                    updateSubtask({
                      id: taskId,
                      status: "completed",
                      subagent_type: parsed.subagent_type,
                      result: parsed.result ?? parsed.visibleText,
                      artifact: parsed.artifact,
                      quality: parsed.quality,
                    });
                  } else if (parsed?.status === "failed") {
                    updateSubtask({
                      id: taskId,
                      status: "failed",
                      subagent_type: parsed.subagent_type,
                      error: parsed.error ?? parsed.visibleText,
                    });
                  } else if (parsed?.status === "timed_out") {
                    updateSubtask({
                      id: taskId,
                      status: "failed",
                      subagent_type: parsed.subagent_type,
                      error: parsed.error ?? parsed.visibleText,
                    });
                  } else {
                    updateSubtask({
                      id: taskId,
                      status: "in_progress",
                    });
                  }
                }
              }
            }
            const results: React.ReactNode[] = [];
            for (const message of group.messages.filter(
              (message) => message.type === "ai",
            )) {
              if (hasReasoning(message)) {
                results.push(
                  <MessageGroup
                    key={"thinking-group-" + message.id}
                    messages={[message]}
                    isLoading={thread.isLoading}
                  />,
                );
              }
              results.push(
                <div
                  key="subtask-count"
                  className="text-muted-foreground font-norma pt-2 text-sm"
                >
                  {t.subtasks.executing(tasks.size)}
                </div>,
              );
              const taskIds = message.tool_calls?.map(
                (toolCall) => toolCall.id,
              );
              for (const taskId of taskIds ?? []) {
                results.push(
                  <SubtaskCard
                    key={"task-group-" + taskId}
                    taskId={taskId!}
                    isLoading={thread.isLoading}
                  />,
                );
              }
            }
            return (
              <div
                key={"subtask-group-" + group.id}
                className="relative z-1 flex flex-col gap-2"
              >
                {results}
              </div>
            );
          }
          return (
            <MessageGroup
              key={"group-" + group.id}
              messages={group.messages}
              isLoading={thread.isLoading}
            />
          );
        })}
        {thread.isLoading && <StreamingIndicator className="my-4" />}
        <div style={{ height: `${paddingBottom}px` }} />
      </ConversationContent>
    </Conversation>
  );
}
