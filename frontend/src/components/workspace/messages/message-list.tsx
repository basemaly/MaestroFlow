import type { BaseStream } from "@langchain/langgraph-sdk/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  Conversation,
  ConversationContent,
} from "@/components/ai-elements/conversation";
import { apiFetch } from "@/core/api/fetch";
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

// Virtualization constants
const VIRTUAL_BUFFER_SIZE = 5; // Number of items to render outside visible area
const ESTIMATED_ITEM_HEIGHT = 200; // Rough estimate for initial calculations

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
  const grouped = useMemo(() => groupMessages(messages, (group) => group), [messages]);
  // Track which threads we've already fetched quality scores for to avoid redundant requests.
  const fetchedThreadsRef = useRef(new Set<string>());

  // Scroll progress minimap — tracks position and lets the user jump across long threads.
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [isScrollable, setIsScrollable] = useState(false);
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);
  const groupElementsRef = useRef(new Map<string, HTMLDivElement>());

  // Virtualization state
  const [containerHeight, setContainerHeight] = useState(0);
  const [scrollTop, setScrollTop] = useState(0);
  const [itemHeights, setItemHeights] = useState(new Map<string, number>());
  const virtualContainerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;
    // StickToBottom renders an inner scroll container — find it via capture
    const update = (e: Event) => {
      const el = e.target as HTMLElement;
      if (!el || typeof el.scrollTop !== "number") return;
      const scrollable = el.scrollHeight - el.clientHeight;
      setIsScrollable(scrollable > 80);
      setScrollProgress(scrollable > 0 ? el.scrollTop / scrollable : 1);
      setScrollTop(el.scrollTop);
      setContainerHeight(el.clientHeight);
      const containerRect = wrapper.getBoundingClientRect();
      const midpoint = containerRect.top + (containerRect.height * 0.32);
      let closest: { id: string; distance: number } | null = null;
      for (const [id, node] of groupElementsRef.current) {
        const rect = node.getBoundingClientRect();
        const distance = Math.abs(rect.top - midpoint);
        if (!closest || distance < closest.distance) {
          closest = { id, distance };
        }
      }
      if (closest) {
        setActiveGroupId(closest.id);
      }
    };
    wrapper.addEventListener("scroll", update, { passive: true, capture: true });
    return () => wrapper.removeEventListener("scroll", update, { capture: true });
  }, []);

  // Virtualization: Calculate visible range
  const { visibleRange, totalHeight, startOffset } = useMemo(() => {
    if (grouped.length === 0) {
      return { visibleRange: { start: 0, end: 0 }, totalHeight: 0, startOffset: 0 };
    }

    const startIndex = Math.max(0, Math.floor(scrollTop / ESTIMATED_ITEM_HEIGHT) - VIRTUAL_BUFFER_SIZE);
    const endIndex = Math.min(
      grouped.length - 1,
      Math.ceil((scrollTop + containerHeight) / ESTIMATED_ITEM_HEIGHT) + VIRTUAL_BUFFER_SIZE
    );

    let currentOffset = 0;
    let totalHeight = 0;

    // Calculate total height and start offset
    for (let i = 0; i < grouped.length; i++) {
      const group = grouped[i];
      if (!group) continue;
      const groupKey = group.id ?? `group-${group.type}-${group.messages?.[0]?.id ?? "unknown"}`;
      const height = itemHeights.get(groupKey) ?? ESTIMATED_ITEM_HEIGHT;
      if (i < startIndex) {
        currentOffset += height;
      }
      totalHeight += height;
    }

    return {
      visibleRange: { start: startIndex, end: endIndex },
      totalHeight,
      startOffset: currentOffset,
    };
  }, [grouped, scrollTop, containerHeight, itemHeights]);

  // Virtualization: Update item heights when elements are rendered
  const updateItemHeight = useCallback((groupKey: string, height: number) => {
    setItemHeights(prev => {
      if (prev.get(groupKey) !== height) {
        const newMap = new Map(prev);
        newMap.set(groupKey, height);
        return newMap;
      }
      return prev;
    });
  }, []);

  if (thread.isThreadLoading && messages.length === 0) {
    return <MessageListSkeleton />;
  }

  const minimapTone = (groupType: string) => {
    switch (groupType) {
      case "human":
        return "bg-stone-500/50";
      case "assistant":
      case "assistant:clarification":
        return "bg-blue-500/55";
      case "assistant:present-files":
        return "bg-emerald-500/55";
      case "assistant:subagent":
        return "bg-violet-500/55";
      default:
        return "bg-slate-400/45";
    }
  };

  return (
    <div ref={wrapperRef} className="relative size-full">
      <div
        className="absolute right-2 top-12 z-10 flex h-[calc(100%-7rem)] w-6 flex-col items-center justify-center transition-opacity duration-300"
        style={{ opacity: isScrollable ? 1 : 0 }}
      >
        <div className="relative h-full w-1 rounded-full bg-border/25">
          {grouped.map((group, index) => {
            const top = grouped.length <= 1 ? 0 : (index / Math.max(grouped.length - 1, 1)) * 100;
            const groupKey = group.id ?? `group-${index}`;
            return (
              <button
                key={`minimap-${groupKey}`}
                type="button"
                aria-label={`Jump to ${group.type}`}
                className={cn(
                  "absolute left-1/2 h-3 w-3 -translate-x-1/2 rounded-full border border-white/70 shadow-sm transition",
                  minimapTone(group.type),
                  activeGroupId === groupKey && "scale-125 ring-2 ring-amber-400/35",
                )}
                style={{ top: `calc(${top}% - 6px)` }}
                onClick={() => {
                  const target = groupElementsRef.current.get(groupKey);
                  target?.scrollIntoView({ behavior: "smooth", block: "center" });
                }}
              />
            );
          })}
          <div
            className="pointer-events-none absolute left-1/2 w-4 -translate-x-1/2 rounded-full border border-amber-400/30 bg-amber-400/15"
            style={{
              top: `${scrollProgress * (100 - 14)}%`,
              height: "14%",
              minHeight: "36px",
            }}
          />
        </div>
      </div>
      <Conversation
        className={cn("flex size-full flex-col justify-center", className)}
      >
      <ConversationContent className="mx-auto w-full max-w-(--container-width-md) gap-8 pt-12">
        {/* Virtualized container for large message lists */}
        <div
          ref={virtualContainerRef}
          className="relative"
          style={{ height: totalHeight || 'auto' }}
        >
          {grouped.slice(visibleRange.start, visibleRange.end + 1).map((group, virtualIndex) => {
            const actualIndex = visibleRange.start + virtualIndex;
            const groupKey = group.id ?? `group-${group.type}-${group.messages[0]?.id ?? "unknown"}`;

            // Calculate absolute position for this item
            let currentOffset = 0;
            for (let i = 0; i < actualIndex; i++) {
              const group = grouped[i];
              if (!group) continue;
              const key = group.id ?? `group-${group.type}-${group.messages?.[0]?.id ?? "unknown"}`;
              currentOffset += itemHeights.get(key) ?? ESTIMATED_ITEM_HEIGHT;
            }

            const setGroupElement = (node: HTMLDivElement | null) => {
              if (node) {
                groupElementsRef.current.set(groupKey, node);
                // Update height measurement
                const rect = node.getBoundingClientRect();
                if (rect.height > 0) {
                  updateItemHeight(groupKey, rect.height);
                }
              } else {
                groupElementsRef.current.delete(groupKey);
              }
            };

            let content: React.ReactNode = null;

            if (group.type === "human" || group.type === "assistant") {
              content = (
                <div className="space-y-0">
                  {group.messages.map((msg) => (
                    <MessageListItem
                      key={`${group.id}/${msg.id}`}
                      message={msg}
                      isLoading={thread.isLoading}
                    />
                  ))}
                </div>
              );
            } else if (group.type === "assistant:clarification") {
              const message = group.messages[0];
              if (message && hasContent(message)) {
                content = (
                  <MarkdownContent
                    content={extractContentFromMessage(message)}
                    isLoading={thread.isLoading}
                    rehypePlugins={rehypePlugins}
                  />
                );
              }
            } else if (group.type === "assistant:present-files") {
              const files: string[] = [];
              for (const message of group.messages) {
                if (hasPresentFiles(message)) {
                  const presentFiles = extractPresentFilesFromMessage(message);
                  files.push(...presentFiles);
                }
              }
              content = (
                <div className="w-full">
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
              content = (
                <div className="relative z-1 flex flex-col gap-2">
                  {results}
                </div>
              );
            } else {
              content = (
                <MessageGroup
                  messages={group.messages}
                  isLoading={thread.isLoading}
                />
              );
            }

            return content ? (
              <div
                key={`virtual-${groupKey}`}
                ref={setGroupElement}
                className="absolute left-0 right-0"
                style={{
                  top: currentOffset,
                  transform: `translateY(${startOffset}px)`,
                }}
              >
                {content}
              </div>
            ) : null;
          })}
        </div>

        {/* Fallback for small lists - render all items normally */}
        {grouped.length <= VIRTUAL_BUFFER_SIZE * 2 && (
          <div className="hidden">
            {grouped.map((group) => {
              const groupKey = group.id ?? `group-${group.type}-${group.messages[0]?.id ?? "unknown"}`;
              const setGroupElement = (node: HTMLDivElement | null) => {
                if (node) {
                  groupElementsRef.current.set(groupKey, node);
                } else {
                  groupElementsRef.current.delete(groupKey);
                }
              };

              if (group.type === "human" || group.type === "assistant") {
                return (
                  <div key={`fallback-${groupKey}`} ref={setGroupElement} className="space-y-0">
                    {group.messages.map((msg) => (
                      <MessageListItem
                        key={`${group.id}/${msg.id}`}
                        message={msg}
                        isLoading={thread.isLoading}
                      />
                    ))}
                  </div>
                );
              } else if (group.type === "assistant:clarification") {
                const message = group.messages[0];
                if (message && hasContent(message)) {
                  return (
                    <div key={`fallback-${group.id}`} ref={setGroupElement}>
                      <MarkdownContent
                        content={extractContentFromMessage(message)}
                        isLoading={thread.isLoading}
                        rehypePlugins={rehypePlugins}
                      />
                    </div>
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
                  <div className="w-full" key={`fallback-${group.id}`} ref={setGroupElement}>
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
                        key={"thinking-fallback-" + message.id}
                        messages={[message]}
                        isLoading={thread.isLoading}
                      />,
                    );
                  }
                  results.push(
                    <div
                      key="subtask-count-fallback"
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
                        key={"task-fallback-" + taskId}
                        taskId={taskId!}
                        isLoading={thread.isLoading}
                      />,
                    );
                  }
                }
                return (
                  <div
                    key={"subtask-fallback-" + group.id}
                    ref={setGroupElement}
                    className="relative z-1 flex flex-col gap-2"
                  >
                    {results}
                  </div>
                );
              }
              return (
                <div key={`fallback-${group.id}`} ref={setGroupElement}>
                  <MessageGroup
                    messages={group.messages}
                    isLoading={thread.isLoading}
                  />
                </div>
              );
            })}
          </div>
        )}

        {thread.isLoading && <StreamingIndicator className="my-4" />}
        <div style={{ height: `${paddingBottom}px` }} />
      </ConversationContent>
      </Conversation>
    </div>
  );
}
