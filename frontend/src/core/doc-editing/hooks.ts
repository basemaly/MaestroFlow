import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getDocEditRun,
  listDocEditRuns,
  selectDocEditVersion,
  startDocEditRun,
  uploadDocEditFile,
} from "./api";

export function useDocEditRuns() {
  return useQuery({
    queryKey: ["doc-edit-runs"],
    queryFn: listDocEditRuns,
    staleTime: 15_000,
  });
}

export function useDocEditRun(runId?: string) {
  return useQuery({
    queryKey: ["doc-edit-run", runId],
    queryFn: () => getDocEditRun(runId!),
    enabled: !!runId,
    staleTime: 15_000,
  });
}

export function useStartDocEditRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: startDocEditRun,
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: ["doc-edit-runs"] });
      void queryClient.setQueryData(["doc-edit-run", run.run_id], run);
    },
  });
}

export function useSelectDocEditVersion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, versionId }: { runId: string; versionId: string }) =>
      selectDocEditVersion(runId, versionId),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: ["doc-edit-runs"] });
      void queryClient.setQueryData(["doc-edit-run", run.run_id], run);
    },
  });
}

export function useUploadDocEditFile() {
  return useMutation({
    mutationFn: uploadDocEditFile,
  });
}
