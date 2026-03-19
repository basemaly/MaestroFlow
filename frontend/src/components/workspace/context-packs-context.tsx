"use client";

import { Layers3Icon, XIcon } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { OpenVikingContextPack } from "@/core/openviking";

const STORAGE_KEY = "maestroflow.workspace.context-packs.v1";

export interface WorkspaceContextPack extends OpenVikingContextPack {
  attached_at: string;
  scope: string;
  source: "openviking" | "manual";
}

interface WorkspaceContextPacksValue {
  packs: WorkspaceContextPack[];
  attachPack: (pack: OpenVikingContextPack, scope?: string) => void;
  attachPacks: (packs: OpenVikingContextPack[], scope?: string) => void;
  detachPack: (packId: string) => void;
  clearPacks: () => void;
}

const WorkspaceContextPacksContext = createContext<WorkspaceContextPacksValue | undefined>(undefined);

function readPacks(): WorkspaceContextPack[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is WorkspaceContextPack => {
      if (!item || typeof item !== "object") return false;
      const record = item as Record<string, unknown>;
      return typeof record.pack_id === "string" && typeof record.title === "string";
    });
  } catch {
    return [];
  }
}

function writePacks(packs: WorkspaceContextPack[]): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(packs));
}

function uniquePackKey(pack: Pick<OpenVikingContextPack, "pack_id" | "fingerprint" | "source_url" | "title">): string {
  const candidates = [pack.fingerprint?.trim(), pack.source_url?.trim(), pack.pack_id, pack.title];
  return candidates.find((value) => typeof value === "string" && value.trim().length > 0) ?? pack.pack_id ?? pack.title;
}

export function WorkspaceContextPacksProvider({ children }: { children: React.ReactNode }) {
  const [packs, setPacks] = useState<WorkspaceContextPack[]>([]);

  useEffect(() => {
    setPacks(readPacks());
  }, []);

  useEffect(() => {
    writePacks(packs);
  }, [packs]);

  const attachPack = useCallback((pack: OpenVikingContextPack, scope = "workspace") => {
    const next: WorkspaceContextPack = {
      ...pack,
      source: "openviking",
      scope,
      attached_at: new Date().toISOString(),
    };
    setPacks((current) => {
      const key = uniquePackKey(pack);
      const filtered = current.filter((item) => uniquePackKey(item) !== key);
      return [next, ...filtered];
    });
  }, []);

  const attachPacks = useCallback((incoming: OpenVikingContextPack[], scope = "workspace") => {
    if (incoming.length === 0) {
      return;
    }
    const attachedAt = new Date().toISOString();
    setPacks((current) => {
      const seen = new Set(current.map((item) => uniquePackKey(item)));
      const next = [...current];
      for (const pack of incoming) {
        const key = uniquePackKey(pack);
        const normalized: WorkspaceContextPack = {
          ...pack,
          source: "openviking",
          scope,
          attached_at: attachedAt,
        };
        if (seen.has(key)) {
          const index = next.findIndex((item) => uniquePackKey(item) === key);
          if (index >= 0) {
            next[index] = normalized;
          }
          continue;
        }
        next.unshift(normalized);
        seen.add(key);
      }
      return next;
    });
  }, []);

  const detachPack = useCallback((packId: string) => {
    setPacks((current) => current.filter((pack) => pack.pack_id !== packId));
  }, []);

  const clearPacks = useCallback(() => {
    setPacks([]);
  }, []);

  const value = useMemo<WorkspaceContextPacksValue>(
    () => ({ packs, attachPack, attachPacks, detachPack, clearPacks }),
    [attachPack, attachPacks, clearPacks, detachPack, packs],
  );

  return (
    <WorkspaceContextPacksContext.Provider value={value}>
      {children}
    </WorkspaceContextPacksContext.Provider>
  );
}

export function useWorkspaceContextPacks() {
  const context = useContext(WorkspaceContextPacksContext);
  if (!context) {
    throw new Error("useWorkspaceContextPacks must be used within WorkspaceContextPacksProvider");
  }
  return context;
}

export function WorkspaceContextPackChips() {
  const { packs, detachPack, clearPacks } = useWorkspaceContextPacks();

  if (packs.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Badge variant="outline" className="gap-1 rounded-full text-[10px]">
        <Layers3Icon className="size-3" />
        {packs.length} pack{packs.length === 1 ? "" : "s"}
      </Badge>
      {packs.map((pack) => (
        <div
          key={pack.pack_id}
          className="inline-flex items-center gap-1 rounded-full border border-border/60 bg-background/70 px-2 py-1 text-[11px]"
        >
          <span className="max-w-[10rem] truncate">{pack.title}</span>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="size-4 rounded-full text-muted-foreground hover:text-foreground"
            onClick={() => detachPack(pack.pack_id)}
            aria-label={`Remove ${pack.title}`}
          >
            <XIcon className="size-3" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="h-7 rounded-full px-2 text-[10px] text-muted-foreground"
        onClick={clearPacks}
      >
        Clear packs
      </Button>
    </div>
  );
}
