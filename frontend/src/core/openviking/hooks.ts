import { useMutation, useQuery } from "@tanstack/react-query";

import {
  attachOpenVikingContextPacks,
  detachOpenVikingContextPack,
  getOpenVikingConfig,
  searchOpenVikingContextPacks,
  syncOpenVikingContextPacks,
} from "./api";
import type { OpenVikingConfigResponse, OpenVikingContextPack } from "./types";

export function useOpenVikingConfig(initialData?: OpenVikingConfigResponse) {
  return useQuery({
    queryKey: ["openviking", "config"],
    queryFn: getOpenVikingConfig,
    initialData,
    initialDataUpdatedAt: initialData ? Date.now() : undefined,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useOpenVikingSearch(input?: {
  query?: string;
  top_k?: number;
  source_key?: string;
}) {
  return useQuery({
    queryKey: ["openviking", "packs", input ?? {}],
    queryFn: () => searchOpenVikingContextPacks(input ?? {}),
    enabled: Boolean((input?.query ?? "").trim() || input?.source_key),
    staleTime: 0,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useAttachOpenVikingContextPacks() {
  return useMutation({
    mutationFn: (input: { packs: OpenVikingContextPack[]; scope?: string; project_key?: string }) =>
      attachOpenVikingContextPacks(input),
  });
}

export function useDetachOpenVikingContextPack() {
  return useMutation({
    mutationFn: (input: { pack_id: string; scope?: string; project_key?: string }) =>
      detachOpenVikingContextPack(input),
  });
}

export function useSyncOpenVikingContextPacks() {
  return useMutation({
    mutationFn: (input?: { scope?: string; project_key?: string }) =>
      syncOpenVikingContextPacks(input),
  });
}
