import { useMutation, useQuery } from "@tanstack/react-query";

import { createBrowserRuntimeJob, getBrowserRuntimeConfig, getBrowserRuntimeJob, listBrowserRuntimeJobs } from "./api";
import type { BrowserJobRequest, BrowserRuntimeConfigResponse, BrowserRuntimeJobsResponse } from "./types";

export function useBrowserRuntimeConfig(initialData?: BrowserRuntimeConfigResponse) {
  return useQuery({
    queryKey: ["browser-runtime", "config"],
    queryFn: getBrowserRuntimeConfig,
    initialData,
    initialDataUpdatedAt: initialData ? Date.now() : undefined,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useBrowserRuntimeJobs(initialData?: BrowserRuntimeJobsResponse["jobs"]) {
  return useQuery({
    queryKey: ["browser-runtime", "jobs"],
    queryFn: async () => (await listBrowserRuntimeJobs()).jobs,
    initialData,
    initialDataUpdatedAt: initialData ? Date.now() : undefined,
    staleTime: 10_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useCreateBrowserRuntimeJob() {
  return useMutation({
    mutationFn: (input: BrowserJobRequest) => createBrowserRuntimeJob(input),
  });
}

export function useBrowserRuntimeJob(jobId?: string) {
  return useQuery({
    queryKey: ["browser-runtime", "job", jobId],
    queryFn: () => getBrowserRuntimeJob(jobId!),
    enabled: Boolean(jobId),
    staleTime: 0,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}
