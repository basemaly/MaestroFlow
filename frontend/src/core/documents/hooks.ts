import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createDocumentQuickAction,
  createDocumentSnapshot,
  createDocument,
  deleteDocumentQuickAction,
  getDocument,
  listDocuments,
  listDocumentQuickActions,
  listDocumentSnapshots,
  restoreDocumentSnapshot,
  transformDocumentSelection,
  updateDocument,
} from "./api";
import type { DocumentQuickActionsListResponse, DocumentSnapshotsListResponse, DocumentsListResponse } from "./types";

export function useDocuments(initialData?: DocumentsListResponse) {
  return useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    initialData,
    initialDataUpdatedAt: initialData ? Date.now() : undefined,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useDocument(docId?: string) {
  return useQuery({
    queryKey: ["document", docId],
    queryFn: () => getDocument(docId!),
    enabled: !!docId,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useCreateDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createDocument,
    onSuccess: (document) => {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      void queryClient.setQueryData(["document", document.doc_id], document);
    },
  });
}

export function useUpdateDocument(docId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: Parameters<typeof updateDocument>[1]) => updateDocument(docId!, input),
    onSuccess: (document) => {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      void queryClient.setQueryData(["document", document.doc_id], document);
    },
  });
}

export function useTransformDocument(docId?: string) {
  return useMutation({
    mutationFn: (input: Parameters<typeof transformDocumentSelection>[1]) =>
      transformDocumentSelection(docId!, input),
  });
}

export function useDocumentQuickActions(initialData?: DocumentQuickActionsListResponse) {
  return useQuery({
    queryKey: ["document-quick-actions"],
    queryFn: listDocumentQuickActions,
    initialData,
    initialDataUpdatedAt: initialData ? Date.now() : undefined,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useCreateDocumentQuickAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createDocumentQuickAction,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["document-quick-actions"] });
    },
  });
}

export function useDeleteDocumentQuickAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteDocumentQuickAction,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["document-quick-actions"] });
    },
  });
}

export function useDocumentSnapshots(docId?: string, initialData?: DocumentSnapshotsListResponse) {
  return useQuery({
    queryKey: ["document-snapshots", docId],
    queryFn: () => listDocumentSnapshots(docId!),
    enabled: Boolean(docId),
    initialData,
    initialDataUpdatedAt: initialData ? Date.now() : undefined,
    staleTime: 30_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useCreateDocumentSnapshot(docId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: Parameters<typeof createDocumentSnapshot>[1]) => createDocumentSnapshot(docId!, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["document-snapshots", docId] });
    },
  });
}

export function useRestoreDocumentSnapshot(docId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (snapshotId: string) => restoreDocumentSnapshot(docId!, snapshotId),
    onSuccess: (document) => {
      void queryClient.invalidateQueries({ queryKey: ["document-snapshots", docId] });
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      void queryClient.setQueryData(["document", document.doc_id], document);
    },
  });
}
