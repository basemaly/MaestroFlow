"use client";

import { useQueryClient } from "@tanstack/react-query";
import { BookOpenTextIcon, BotIcon, FilePenLineIcon, MessagesSquare } from "lucide-react";
import { BookOpenTextIcon, BotIcon, FlaskConicalIcon, FilePenLineIcon, MessagesSquare } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ExecutiveIcon } from "@/components/workspace/executive-icon";
import { listAgents } from "@/core/agents";
import { listDocEditRuns } from "@/core/doc-editing/api";
import { listDocuments } from "@/core/documents/api";
import { useI18n } from "@/core/i18n/hooks";

function NavItem({
  href,
  icon: Icon,
  label,
  isActive,
  isSidebarOpen,
  iconClassName,
}: {
  href: string;
  icon: React.ElementType;
  label: string;
  isActive: boolean;
  isSidebarOpen: boolean;
  iconClassName?: string;
}) {
  return (
    <SidebarMenuItem>
      <Tooltip>
        <TooltipTrigger asChild>
          <SidebarMenuButton isActive={isActive} asChild>
            <Link className="text-muted-foreground" href={href}>
              <Icon className={iconClassName} />
              <span>{label}</span>
            </Link>
          </SidebarMenuButton>
        </TooltipTrigger>
        {!isSidebarOpen && (
          <TooltipContent side="right">{label}</TooltipContent>
        )}
      </Tooltip>
    </SidebarMenuItem>
  );
}

export function WorkspaceNavChatList() {
  const { t } = useI18n();
  const pathname = usePathname();
  const { open: isSidebarOpen } = useSidebar();
  const queryClient = useQueryClient();

  useEffect(() => {
    void queryClient.prefetchQuery({
      queryKey: ["agents"],
      queryFn: listAgents,
      staleTime: 60_000,
    });
    void queryClient.prefetchQuery({
      queryKey: ["documents"],
      queryFn: listDocuments,
      staleTime: 60_000,
    });
    void queryClient.prefetchQuery({
      queryKey: ["doc-edit-runs"],
      queryFn: listDocEditRuns,
      staleTime: 60_000,
    });
  }, [queryClient]);

  return (
    <SidebarGroup className="pt-1">
      <SidebarMenu>
        <NavItem
          href="/workspace/executive"
          icon={ExecutiveIcon}
          label={t.sidebar.executive}
          isActive={pathname.startsWith("/workspace/executive")}
          isSidebarOpen={isSidebarOpen}
          iconClassName="text-amber-500"
        />
        <NavItem
          href="/workspace/chats"
          icon={MessagesSquare}
          label={t.sidebar.chats}
          isActive={pathname === "/workspace/chats"}
          isSidebarOpen={isSidebarOpen}
        />
        <NavItem
          href="/workspace/docs"
          icon={BookOpenTextIcon}
          label={t.sidebar.documents}
          isActive={pathname.startsWith("/workspace/docs")}
          isSidebarOpen={isSidebarOpen}
        />
        <NavItem
          href="/workspace/doc-edits"
          icon={FilePenLineIcon}
          label={t.sidebar.docEdits}
          isActive={pathname.startsWith("/workspace/doc-edits")}
          isSidebarOpen={isSidebarOpen}
        />
        <NavItem
          href="/workspace/autoresearch"
          icon={FlaskConicalIcon}
          label={t.sidebar.autoresearch}
          isActive={pathname.startsWith("/workspace/autoresearch")}
          isSidebarOpen={isSidebarOpen}
        />
        <NavItem
          href="/workspace/agents"
          icon={BotIcon}
          label={t.sidebar.agentPresets}
          isActive={pathname.startsWith("/workspace/agents")}
          isSidebarOpen={isSidebarOpen}
        />
      </SidebarMenu>
    </SidebarGroup>
  );
}
