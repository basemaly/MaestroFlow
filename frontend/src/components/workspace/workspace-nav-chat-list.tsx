"use client";

import { BookmarkIcon, BotIcon, FilePenLineIcon, MessagesSquare, ShieldCheckIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { SnippetShelfContent } from "@/components/workspace/snippet-shelf";
import { useI18n } from "@/core/i18n/hooks";

export function WorkspaceNavChatList() {
  const { t } = useI18n();
  const pathname = usePathname();
  // Defer Sheet render to client-only to avoid Radix sequential-ID hydration mismatch
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <SidebarGroup className="pt-1">
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton isActive={pathname === "/workspace/chats"} asChild>
            <Link className="text-muted-foreground" href="/workspace/chats">
              <MessagesSquare />
              <span>{t.sidebar.chats}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={pathname.startsWith("/workspace/agents")}
            asChild
          >
            <Link className="text-muted-foreground" href="/workspace/agents">
              <BotIcon />
              <span>{t.sidebar.agents}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={pathname.startsWith("/workspace/doc-edits")}
            asChild
          >
            <Link className="text-muted-foreground" href="/workspace/doc-edits">
              <FilePenLineIcon />
              <span>{t.sidebar.docEdits}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={pathname.startsWith("/workspace/executive")}
            asChild
          >
            <Link className="text-muted-foreground" href="/workspace/executive">
              <ShieldCheckIcon />
              <span>{t.sidebar.executive}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          {mounted ? (
            <Sheet>
              <SheetTrigger asChild>
                <SidebarMenuButton className="text-muted-foreground">
                  <BookmarkIcon />
                  <span>Snippets</span>
                </SidebarMenuButton>
              </SheetTrigger>
              <SheetContent side="right" className="flex w-[400px] flex-col sm:w-[440px]">
                <SnippetShelfContent />
              </SheetContent>
            </Sheet>
          ) : (
            <SidebarMenuButton className="text-muted-foreground" disabled>
              <BookmarkIcon />
              <span>Snippets</span>
            </SidebarMenuButton>
          )}
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  );
}
