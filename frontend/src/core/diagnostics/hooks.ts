import { useQuery } from "@tanstack/react-query";

import {
  getDiagnosticsComponentLogs,
  getDiagnosticsOverview,
  listDiagnosticsEvents,
  listDiagnosticsLogComponents,
  listDiagnosticsRequests,
  listDiagnosticsTraces,
} from "./api";

export function useDiagnosticsOverview(enabled = true) {
  return useQuery({
    queryKey: ["diagnostics", "overview"],
    queryFn: getDiagnosticsOverview,
    enabled,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useDiagnosticsLogComponents(enabled = true) {
  return useQuery({
    queryKey: ["diagnostics", "logs", "components"],
    queryFn: listDiagnosticsLogComponents,
    enabled,
    staleTime: 60_000,
  });
}

export function useDiagnosticsComponentLogs(componentId: string | null, lines = 120, contains?: string, enabled = true) {
  return useQuery({
    queryKey: ["diagnostics", "logs", componentId, lines, contains ?? ""],
    queryFn: () => getDiagnosticsComponentLogs({ componentId: componentId!, lines, contains }),
    enabled: enabled && Boolean(componentId),
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  });
}

export function useDiagnosticsRequests(params?: {
  limit?: number;
  pathContains?: string;
  status?: number;
  requestId?: string;
  traceId?: string;
}, enabled = true) {
  return useQuery({
    queryKey: ["diagnostics", "requests", params],
    queryFn: () => listDiagnosticsRequests(params),
    enabled,
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  });
}

export function useDiagnosticsTraces(params?: {
  limit?: number;
  traceId?: string;
}, enabled = true) {
  return useQuery({
    queryKey: ["diagnostics", "traces", params],
    queryFn: () => listDiagnosticsTraces(params),
    enabled,
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  });
}

export function useDiagnosticsEvents(params?: {
  limit?: number;
  kind?: "audit" | "approval";
}, enabled = true) {
  return useQuery({
    queryKey: ["diagnostics", "events", params],
    queryFn: () => listDiagnosticsEvents(params),
    enabled,
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  });
}
