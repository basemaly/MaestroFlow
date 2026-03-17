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
        <ExecutiveConsole />
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
