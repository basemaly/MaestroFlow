"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { Toaster } from "sonner";

import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { WorkspaceBackground } from "@/components/workspace/workspace-background";
import { WorkspaceSidebar } from "@/components/workspace/workspace-sidebar";
import { getLocalSettings, useLocalSettings } from "@/core/settings";

const queryClient = new QueryClient();

export default function WorkspaceLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [settings, setSettings] = useLocalSettings();
  const [open, setOpen] = useState(false); // SSR default: open (matches server render)
  useLayoutEffect(() => {
    // Runs synchronously before first paint on the client — no visual flash
    setOpen(!getLocalSettings().layout.sidebar_collapsed);
  }, []);
  useEffect(() => {
    setOpen(!settings.layout.sidebar_collapsed);
  }, [settings.layout.sidebar_collapsed]);
  const handleOpenChange = useCallback(
    (open: boolean) => {
      setOpen(open);
      setSettings("layout", { sidebar_collapsed: !open });
    },
    [setSettings],
  );
  return (
    <QueryClientProvider client={queryClient}>
      <SidebarProvider
        className="h-screen"
        open={open}
        onOpenChange={handleOpenChange}
      >
        <WorkspaceSidebar />
        <SidebarInset className="relative isolate min-w-0 overflow-hidden">
          <WorkspaceBackground />
          {children}
        </SidebarInset>
      </SidebarProvider>
      <Toaster position="top-center" />
    </QueryClientProvider>
  );
}
