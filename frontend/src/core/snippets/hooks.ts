import { useCallback, useEffect, useState } from "react";

import { loadSnippets, saveSnippets } from "./store";
import type { Snippet } from "./types";

let nextId = 1;
function generateId(): string {
  return `snip_${Date.now()}_${nextId++}`;
}

export function useSnippets() {
  const [snippets, setSnippets] = useState<Snippet[]>([]);

  useEffect(() => {
    setSnippets(loadSnippets());
  }, []);

  const persist = useCallback((next: Snippet[]) => {
    setSnippets(next);
    saveSnippets(next);
  }, []);

  const addSnippet = useCallback(
    (text: string, label?: string, tags?: string[], sourceThreadId?: string) => {
      const snippet: Snippet = {
        id: generateId(),
        text,
        label: label ?? text.slice(0, 60).replace(/\n/g, " "),
        tags: tags ?? [],
        source_thread_id: sourceThreadId,
        created_at: Date.now(),
      };
      persist([snippet, ...snippets]);
      return snippet;
    },
    [snippets, persist],
  );

  const removeSnippet = useCallback(
    (id: string) => {
      persist(snippets.filter((s) => s.id !== id));
    },
    [snippets, persist],
  );

  const updateSnippet = useCallback(
    (id: string, updates: Partial<Pick<Snippet, "label" | "tags" | "text">>) => {
      persist(
        snippets.map((s) => (s.id === id ? { ...s, ...updates } : s)),
      );
    },
    [snippets, persist],
  );

  const clearAll = useCallback(() => {
    persist([]);
  }, [persist]);

  return { snippets, addSnippet, removeSnippet, updateSnippet, clearAll };
}
