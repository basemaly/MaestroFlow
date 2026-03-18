import { useQuery } from "@tanstack/react-query";

import { getAutoresearchExperiment, getAutoresearchRegistry, listAutoresearchExperiments } from "./api";
import type { AutoresearchExperimentDetail, AutoresearchRegistryPayload, ExperimentSummary } from "./types";

export function useAutoresearchRegistry(initialData?: AutoresearchRegistryPayload) {
  return useQuery({
    queryKey: ["autoresearch", "registry"],
    queryFn: getAutoresearchRegistry,
    initialData,
    initialDataUpdatedAt: initialData ? Date.now() : undefined,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useAutoresearchExperiments(initialData?: ExperimentSummary[]) {
  return useQuery({
    queryKey: ["autoresearch", "experiments"],
    queryFn: async () => (await listAutoresearchExperiments()).experiments,
    initialData,
    initialDataUpdatedAt: initialData ? Date.now() : undefined,
    staleTime: 15_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useAutoresearchExperiment(experimentId?: string) {
  return useQuery<AutoresearchExperimentDetail>({
    queryKey: ["autoresearch", "experiment", experimentId],
    queryFn: () => getAutoresearchExperiment(experimentId!),
    enabled: Boolean(experimentId),
    staleTime: 15_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}
