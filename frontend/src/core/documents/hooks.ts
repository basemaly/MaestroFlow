import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createDocument,
  getDocument,
  listDocuments,
  transformDocumentSelection,
  updateDocument,
} from "./api";
import type { DocumentsListResponse } from "./types";

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
