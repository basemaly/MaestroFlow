import { useMutation, useQuery } from "@tanstack/react-query";

import {
  getActivepiecesConfig,
  listActivepiecesFlows,
  previewActivepiecesFlow,
  receiveActivepiecesWebhook,
  triggerActivepiecesFlow,
} from "./api";
import type { ActivepiecesConfigResponse, ActivepiecesFlow } from "./types";

export function useActivepiecesConfig(initialData?: ActivepiecesConfigResponse) {
  return useQuery({
    queryKey: ["activepieces", "config"],
    queryFn: getActivepiecesConfig,
    initialData,
    initialDataUpdatedAt: initialData ? Date.now() : undefined,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useActivepiecesFlows(initialData?: ActivepiecesFlow[]) {
  return useQuery({
    queryKey: ["activepieces", "flows"],
    queryFn: async () => (await listActivepiecesFlows()).flows,
    initialData,
    initialDataUpdatedAt: initialData ? Date.now() : undefined,
    staleTime: 30_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function usePreviewActivepiecesFlow() {
  return useMutation({
    mutationFn: (input: { flowId: string; payload: Record<string, unknown> }) =>
      previewActivepiecesFlow(input.flowId, input.payload),
  });
}

export function useTriggerActivepiecesFlow() {
  return useMutation({
    mutationFn: (input: { flowId: string; payload: Record<string, unknown> }) =>
      triggerActivepiecesFlow(input.flowId, input.payload),
  });
}

export function useActivepiecesWebhook() {
  return useMutation({
    mutationFn: (input: { webhookKey: string; payload: Record<string, unknown> }) =>
      receiveActivepiecesWebhook(input.webhookKey, input.payload),
  });
}
