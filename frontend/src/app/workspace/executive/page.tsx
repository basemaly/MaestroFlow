"use client";

import { useEffect } from "react";

import { ExecutiveConsole } from "@/components/workspace/executive-console";
import { ExternalServiceBanner } from "@/components/workspace/external-service-banner";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";

export default function ExecutivePage() {
  const { t } = useI18n();

  useEffect(() => {
    document.title = `Executive - ${t.pages.appName}`;
  }, [t.pages.appName]);

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <ExternalServiceBanner />
        <div className="flex size-full flex-col bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.08),transparent_24%),radial-gradient(circle_at_top_right,rgba(59,130,246,0.05),transparent_22%)]">
          <div className="border-b border-border/70 px-6 py-5">
            <div className="max-w-3xl">
              <div className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
                Executive Console
              </div>
              <div className="mt-2 text-2xl font-semibold tracking-tight">Operational oversight and guarded execution</div>
              <div className="mt-2 text-sm text-muted-foreground">
                Use Executive when you need system status, approvals, operational actions, or a concise recommendation about what to do next.
              </div>
            </div>
          </div>
          <ExecutiveConsole />
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
