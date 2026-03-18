"use client";

import { BookOpenTextIcon, FilePenLineIcon } from "lucide-react";
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
import { useDocuments } from "@/core/documents/hooks";
import { useI18n } from "@/core/i18n/hooks";
import { formatTimeAgo } from "@/core/utils/datetime";

type WritingActivityItem =
  | {
      key: string;
      href: string;
      title: string;
      meta: string;
      updatedAt: string;
      icon: typeof BookOpenTextIcon;
    }
  | {
      key: string;
      href: string;
      title: string;
      meta: string;
      updatedAt: string;
      icon: typeof FilePenLineIcon;
    };

export function RecentWritingActivityList() {
  const { t } = useI18n();
  const pathname = usePathname();
  const { data: documentsData } = useDocuments();
  const { data: runsData } = useDocEditRuns();

  const activities: WritingActivityItem[] = [
    ...(documentsData?.documents ?? []).map((document) => ({
      key: `document-${document.doc_id}`,
      href: `/workspace/docs/${document.doc_id}`,
      title: document.title,
      meta: `${document.status} · ${formatTimeAgo(document.updated_at)}`,
      updatedAt: document.updated_at,
      icon: BookOpenTextIcon,
    })),
    ...(runsData?.runs ?? [])
      .filter((run): run is typeof run & { timestamp: string } => Boolean(run.timestamp))
      .map((run) => ({
        key: `run-${run.run_id}`,
        href: `/workspace/doc-edits/${run.run_id}`,
        title: run.title ?? run.run_id,
        meta: `${run.status} · ${formatTimeAgo(run.timestamp)}`,
        updatedAt: run.timestamp,
        icon: FilePenLineIcon,
      })),
  ]
    .sort((left, right) => {
      return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
    })
    .slice(0, 8);

  if (activities.length === 0) {
    return null;
  }

  return (
    <SidebarGroup>
      <SidebarGroupLabel>{t.sidebar.writing}</SidebarGroupLabel>
      <SidebarGroupContent className="group-data-[collapsible=icon]:pointer-events-none group-data-[collapsible=icon]:-mt-8 group-data-[collapsible=icon]:opacity-0">
        <SidebarMenu>
          {activities.map((activity) => {
            const Icon = activity.icon;
            return (
              <SidebarMenuItem key={activity.key}>
                <SidebarMenuButton className="h-auto py-2" isActive={pathname === activity.href} asChild>
                  <Link className="text-muted-foreground" href={activity.href}>
                    <Icon className="mt-0.5 shrink-0" />
                    <div className="min-w-0">
                      <div className="truncate">{activity.title}</div>
                      <div className="text-xs text-muted-foreground/80">{activity.meta}</div>
                    </div>
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
