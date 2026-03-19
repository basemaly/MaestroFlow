import { useMutation, useQuery } from "@tanstack/react-query";

import {
  createStateSnapshot,
  diffStateSnapshots,
  exportStateSnapshot,
  getStateConfig,
  getStateSnapshot,
  listStateSnapshots,
} from "./api";
import type { StateConfigResponse, StateScope } from "./types";

export function useStateConfig(initialData?: StateConfigResponse) {
  return useQuery({
    queryKey: ["state", "config"],
    queryFn: getStateConfig,
    initialData,
    initialDataUpdatedAt: initialData ? Date.now() : undefined,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useStateSnapshots(input?: {
  scope?: StateScope;
  reference_id?: string;
  state_type?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["state", "snapshots", input ?? {}],
    queryFn: () => listStateSnapshots(input),
    enabled: [input?.scope, input?.reference_id, input?.state_type, input?.limit].some(
      (value) => value !== undefined && value !== null && value !== "",
    ),
    staleTime: 10_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useCreateStateSnapshot() {
  return useMutation({
    mutationFn: createStateSnapshot,
  });
}

export function useStateSnapshot(snapshotId?: string) {
  return useQuery({
    queryKey: ["state", "snapshot", snapshotId],
    queryFn: () => getStateSnapshot(snapshotId!),
    enabled: Boolean(snapshotId),
    staleTime: 0,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useDiffStateSnapshots() {
  return useMutation({
    mutationFn: diffStateSnapshots,
  });
}

export function useExportStateSnapshot() {
  return useMutation({
    mutationFn: exportStateSnapshot,
  });
}
