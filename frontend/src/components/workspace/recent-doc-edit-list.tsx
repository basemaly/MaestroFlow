"use client";

import { FilePenLineIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useDocEditRuns } from "@/core/doc-editing/hooks";
import { useI18n } from "@/core/i18n/hooks";

export function RecentDocEditList() {
  const { t } = useI18n();
  const pathname = usePathname();
  const { data } = useDocEditRuns();
  const runs = data?.runs.slice(0, 8) ?? [];

  if (runs.length === 0) {
    return null;
  }

  return (
    <SidebarGroup>
      <SidebarGroupLabel>{t.sidebar.docEdits}</SidebarGroupLabel>
      <SidebarGroupContent className="group-data-[collapsible=icon]:pointer-events-none group-data-[collapsible=icon]:-mt-8 group-data-[collapsible=icon]:opacity-0">
        <SidebarMenu>
          {runs.map((run) => {
            const href = `/workspace/doc-edits/${run.run_id}`;
            return (
              <SidebarMenuItem key={run.run_id}>
                <SidebarMenuButton isActive={pathname === href} asChild>
                  <Link className="text-muted-foreground" href={href}>
                    <FilePenLineIcon />
                    <span>{run.title ?? run.run_id}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
