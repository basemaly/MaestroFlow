"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRightIcon, MessagesSquareIcon, PlusIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";
import { useThreads } from "@/core/threads/hooks";
import { pathOfThread, titleOfThread } from "@/core/threads/utils";
import { formatTimeAgo } from "@/core/utils/datetime";

export default function ChatsPage() {
  const { t } = useI18n();
  const { data: threads } = useThreads();
  const [search, setSearch] = useState("");

  useEffect(() => {
    document.title = `${t.pages.chats} - ${t.pages.appName}`;
  }, [t.pages.chats, t.pages.appName]);

  const filteredThreads = useMemo(() => {
    return threads?.filter((thread) => {
      return titleOfThread(thread).toLowerCase().includes(search.toLowerCase());
    });
  }, [threads, search]);
  return (
    <WorkspaceContainer>
      <WorkspaceHeader></WorkspaceHeader>
      <WorkspaceBody>
        <div className="flex size-full flex-col bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.06),transparent_24%),radial-gradient(circle_at_top_right,rgba(16,185,129,0.05),transparent_22%)]">
          <header className="mx-auto flex w-full max-w-(--container-width-md) shrink-0 flex-col gap-4 px-4 pt-8">
            <div className="rounded-3xl border border-border/70 bg-background/85 p-5 shadow-sm backdrop-blur">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
                    Chat Desk
                  </div>
                  <div className="text-2xl font-semibold tracking-tight">{t.pages.chats}</div>
                  <div className="max-w-2xl text-sm text-muted-foreground">
                    Return to active threads, search old conversations, or open a fresh one when you need a clean line of work.
                  </div>
                </div>
                <Button asChild>
                  <Link href="/workspace/chats/new">
                    <PlusIcon className="size-4" />
                    New chat
                  </Link>
                </Button>
              </div>
            </div>
            <Input
              type="search"
              className="h-12 w-full max-w-(--container-width-md) text-xl"
              placeholder={t.chats.searchChats}
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </header>
          <main className="min-h-0 flex-1">
            <ScrollArea className="size-full py-4">
              <div className="mx-auto flex size-full max-w-(--container-width-md) flex-col">
                {!threads?.length ? (
                  <div className="rounded-3xl border border-dashed border-border/80 bg-background/70 px-6 py-10 text-center">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-muted/60">
                      <MessagesSquareIcon className="size-7 text-muted-foreground" />
                    </div>
                    <div className="mt-4 text-base font-medium">No chats yet</div>
                    <div className="mt-2 text-sm text-muted-foreground">
                      Start a fresh conversation, then come back here when you want to revisit the thread.
                    </div>
                    <Button asChild className="mt-4">
                      <Link href="/workspace/chats/new">
                        Open a fresh chat
                        <ArrowRightIcon className="size-4" />
                      </Link>
                    </Button>
                  </div>
                ) : filteredThreads?.length === 0 ? (
                  <div className="rounded-3xl border border-dashed border-border/80 bg-background/70 px-6 py-10 text-center text-sm text-muted-foreground">
                    No chats match that search yet.
                  </div>
                ) : filteredThreads?.map((thread) => (
                  <Link
                    key={thread.thread_id}
                    href={pathOfThread(thread.thread_id)}
                  >
                    <div className="flex flex-col gap-2 border-b border-border/70 p-4 transition-colors hover:bg-accent/20">
                      <div>
                        <div>{titleOfThread(thread)}</div>
                      </div>
                      {thread.updated_at && (
                        <div className="text-muted-foreground text-sm">
                          {formatTimeAgo(thread.updated_at)}
                        </div>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            </ScrollArea>
          </main>
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
