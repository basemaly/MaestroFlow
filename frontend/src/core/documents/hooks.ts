import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createDocument,
  getDocument,
  listDocuments,
  transformDocumentSelection,
  updateDocument,
} from "./api";

export function useDocuments() {
  return useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    staleTime: 15_000,
  });
}

export function useDocument(docId?: string) {
  return useQuery({
    queryKey: ["document", docId],
    queryFn: () => getDocument(docId!),
    enabled: !!docId,
    staleTime: 15_000,
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
