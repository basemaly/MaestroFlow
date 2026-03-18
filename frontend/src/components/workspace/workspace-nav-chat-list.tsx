"use client";

import { BotIcon, FilePenLineIcon, MessagesSquare, ShieldCheckIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
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

  return (
    <SidebarGroup className="pt-1">
      <SidebarMenu>
        <NavItem
          href="/workspace/chats"
          icon={MessagesSquare}
          label={t.sidebar.chats}
          isActive={pathname === "/workspace/chats"}
          isSidebarOpen={isSidebarOpen}
        />
        <NavItem
          href="/workspace/agents"
          icon={BotIcon}
          label={t.sidebar.agents}
          isActive={pathname.startsWith("/workspace/agents")}
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
          href="/workspace/executive"
          icon={ShieldCheckIcon}
          label={t.sidebar.executive}
          isActive={pathname.startsWith("/workspace/executive")}
          isSidebarOpen={isSidebarOpen}
          iconClassName="text-amber-500"
        />
      </SidebarMenu>
    </SidebarGroup>
  );
}
