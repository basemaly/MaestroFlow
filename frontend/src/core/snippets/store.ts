import type { Snippet } from "./types";

const STORAGE_KEY = "maestroflow.snippets";

export function loadSnippets(): Snippet[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Snippet[]) : [];
  } catch {
    return [];
  }
}

export function saveSnippets(snippets: Snippet[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(snippets));
}
