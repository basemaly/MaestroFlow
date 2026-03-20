"use client";

import { useEffect, useState } from "react";

import { getBackendBaseURL } from "@/core/config";

export interface SurfSenseSearchSpace {
  id: number;
  name: string;
}

function normalizeSpaces(payload: unknown): SurfSenseSearchSpace[] {
  const rawItems = Array.isArray(payload)
    ? payload
    : Array.isArray((payload as { items?: unknown })?.items)
      ? ((payload as { items: unknown[] }).items ?? [])
      : [];
  return (rawItems as Record<string, unknown>[])
    .map((item) => ({
      id: typeof item.id === "number" ? item.id : Number.NaN,
      name:
        typeof item.name === "string"
          ? item.name
          : typeof item.id === "number"
            ? `Space ${item.id}`
            : "Untitled",
    }))
    .filter((s) => Number.isFinite(s.id));
}

/** Fetches SurfSense search spaces once. Returns empty array if unconfigured or unavailable. */
export function useSurfSenseSearchSpaces() {
  const [spaces, setSpaces] = useState<SurfSenseSearchSpace[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${getBackendBaseURL()}/api/surfsense/search-spaces`)
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: unknown = await res.json();
        setSpaces(normalizeSpaces(data));
        setError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unavailable");
          setSpaces([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  return { spaces, loading, error };
}
