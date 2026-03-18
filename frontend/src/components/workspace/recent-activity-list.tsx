"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BookOpenTextIcon,
  BotIcon,
  CheckCircle2Icon,
  ClipboardCheckIcon,
  FilePenLineIcon,
  MessagesSquareIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

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
import { getExecutiveApprovals, getExecutiveAudit } from "@/core/executive/api";
import { useI18n } from "@/core/i18n/hooks";
import { useThreads } from "@/core/threads/hooks";
import { pathOfThread, titleOfThread } from "@/core/threads/utils";
import { formatTimeAgo } from "@/core/utils/datetime";

type ActivityItem = {
  key: string;
  href: string;
  title: string;
  meta: string;
  updatedAt: string;
  icon: React.ElementType;
  accent?: string;
  priority: number;
};

export function RecentActivityList() {
  const { t } = useI18n();
  const pathname = usePathname();
  const [hydrated, setHydrated] = useState(false);
  const { data: threads = [] } = useThreads();
  const { data: documentsData } = useDocuments();
  const { data: runsData } = useDocEditRuns();
  const approvalsQuery = useQuery({
    queryKey: ["executive", "approvals", "sidebar"],
    queryFn: () => getExecutiveApprovals(),
    staleTime: 30_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  const auditQuery = useQuery({
    queryKey: ["executive", "audit", "sidebar"],
    queryFn: () => getExecutiveAudit(),
    staleTime: 30_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  useEffect(() => {
    setHydrated(true);
  }, []);

  const activities = useMemo<ActivityItem[]>(() => {
    const items: ActivityItem[] = [];

    for (const thread of threads.slice(0, 8)) {
      items.push({
        key: `thread-${thread.thread_id}`,
        href: pathOfThread(thread.thread_id),
        title: titleOfThread(thread),
        meta: "Chat session",
        updatedAt: thread.updated_at ?? thread.created_at ?? new Date().toISOString(),
        icon: MessagesSquareIcon,
        priority: 1,
      });
    }

    for (const document of documentsData?.documents ?? []) {
      items.push({
        key: `document-${document.doc_id}`,
        href: `/workspace/docs/${document.doc_id}`,
        title: document.title,
        meta: `${document.status} · ${formatTimeAgo(document.updated_at)}`,
        updatedAt: document.updated_at,
        icon: BookOpenTextIcon,
        priority: document.status === "active" ? 3 : 2,
      });
    }

    for (const run of runsData?.runs ?? []) {
      if (!run.timestamp) continue;
      items.push({
        key: `revision-${run.run_id}`,
        href: `/workspace/doc-edits/${run.run_id}`,
        title: run.title ?? "Revision session",
        meta: `${run.status} · ${formatTimeAgo(run.timestamp)}`,
        updatedAt: run.timestamp,
        icon: FilePenLineIcon,
        priority: run.status === "awaiting_selection" ? 5 : 3,
      });
    }

    for (const approval of approvalsQuery.data?.approvals ?? []) {
      items.push({
        key: `approval-${approval.approval_id}`,
        href: "/workspace/executive",
        title: approval.preview.summary,
        meta: `Approval needed · ${formatTimeAgo(approval.created_at)}`,
        updatedAt: approval.created_at,
        icon: ClipboardCheckIcon,
        accent: "text-amber-500",
        priority: 8,
      });
    }

    for (const entry of (auditQuery.data?.entries ?? [])
      .filter(
        (item) => item.status !== "succeeded" || item.component_id === "lead_agent",
      )
      .slice(0, 6)) {
      items.push({
        key: `audit-${entry.audit_id}`,
        href: "/workspace/executive",
        title: entry.result_summary || entry.action_id,
        meta: `${entry.component_id} · ${formatTimeAgo(entry.timestamp)}`,
        updatedAt: entry.timestamp,
        icon:
          entry.status === "succeeded"
            ? CheckCircle2Icon
            : entry.component_id === "lead_agent"
              ? BotIcon
              : ClipboardCheckIcon,
        priority:
          entry.status === "failed"
            ? 7
            : entry.component_id === "lead_agent"
              ? 4
              : 2,
      });
    }

    return items
      .sort(
        (left, right) =>
          right.priority - left.priority ||
          new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime(),
      )
      .slice(0, 8);
  }, [approvalsQuery.data?.approvals, auditQuery.data?.entries, documentsData?.documents, runsData?.runs, threads]);

  if (!hydrated || activities.length === 0) {
    return null;
  }

  return (
    <SidebarGroup>
      <SidebarGroupLabel>{t.sidebar.activity}</SidebarGroupLabel>
      <SidebarGroupContent className="group-data-[collapsible=icon]:pointer-events-none group-data-[collapsible=icon]:-mt-8 group-data-[collapsible=icon]:opacity-0">
        <SidebarMenu>
          {activities.map((activity) => {
            const Icon = activity.icon;
            return (
              <SidebarMenuItem key={activity.key}>
                <SidebarMenuButton
                  className="h-auto py-2"
                  isActive={pathname === activity.href}
                  asChild
                >
                  <Link className="text-muted-foreground" href={activity.href}>
                    <Icon className={activity.accent} />
                    <div className="min-w-0">
                      <div className="truncate">{activity.title}</div>
                      <div className="text-xs text-muted-foreground/80">
                        {activity.meta}
                      </div>
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
