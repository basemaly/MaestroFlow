"use client";

import { BookIcon, Loader2Icon, RefreshCwIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { apiFetch } from "@/core/api/fetch";
import { getBackendBaseURL } from "@/core/config";

type CalibreStatusPayload = {
  available: boolean;
  healthy?: boolean;
  configured?: boolean;
  dataset_name?: string;
  dataset_id?: string;
  collection?: string;
  indexed_books?: number;
  indexed_chunks?: number;
  last_sync_at?: string | null;
  last_error?: string | null;
};

const FALLBACK_STATUS: CalibreStatusPayload = {
  available: false,
  configured: false,
  healthy: false,
  dataset_name: "Calibre Library",
  last_error: "Calibre integration is unavailable.",
};

async function readCalibrePayload(
  response: Response,
): Promise<CalibreStatusPayload | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  return (await response.json()) as CalibreStatusPayload;
}

function fallbackFromResponse(
  response: Response,
  message: string,
): CalibreStatusPayload {
  return {
    ...FALLBACK_STATUS,
    last_error: `${message} (${response.status})`,
  };
}

export function CalibreStatus() {
  const [status, setStatus] = useState<CalibreStatusPayload | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const response = await apiFetch(`${getBackendBaseURL()}/api/calibre/status`, {
        cache: "no-store",
      });
      const payload = await readCalibrePayload(response);
      if (!response.ok || !payload) {
        setStatus(fallbackFromResponse(response, "Calibre status endpoint unavailable"));
        return;
      }
      setStatus({
        ...FALLBACK_STATUS,
        ...payload,
        healthy: payload.healthy ?? (payload.available && !payload.last_error),
      });
    } catch (error) {
      setStatus({
        ...FALLBACK_STATUS,
        last_error: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setLoading(false);
    }
  }

  async function sync() {
    setLoading(true);
    try {
      const response = await apiFetch(`${getBackendBaseURL()}/api/calibre/sync`, {
        method: "POST",
      });
      const payload =
        (await readCalibrePayload(response)) ??
        fallbackFromResponse(response, "Calibre sync endpoint unavailable");
      setStatus(payload);
      if (!response.ok || payload.last_error) {
        toast.error(payload.last_error);
      } else {
        toast.success("Calibre library synced");
        // Refresh status after a brief delay to show updated sync time
        setTimeout(() => void load(), 1000);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  }

  async function reindex() {
    setLoading(true);
    try {
      const response = await apiFetch(`${getBackendBaseURL()}/api/calibre/reindex`, {
        method: "POST",
      });
      const payload =
        (await readCalibrePayload(response)) ??
        fallbackFromResponse(response, "Calibre reindex endpoint unavailable");
      setStatus(payload);
      if (!response.ok || payload.last_error) {
        toast.error(payload.last_error);
      } else {
        toast.success("Calibre library reindexed");
        // Refresh status after a brief delay to show updated sync time
        setTimeout(() => void load(), 1000);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  if (!status) {
    return null;
  }

  const shortName = "Calibre Library";
  const syncLabel = status.last_sync_at
    ? (() => {
        const d = new Date(status.last_sync_at);
        const now = new Date();
        const diffMs = now.getTime() - d.getTime();
        const diffMin = Math.floor(diffMs / 60000);
        if (diffMin < 1) return "Synced just now";
        if (diffMin < 60) return `Synced ${diffMin}m ago`;
        const diffH = Math.floor(diffMin / 60);
        if (diffH < 24) return `Synced ${diffH}h ago`;
        return `Synced ${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
      })()
    : null;

  return (
    <div className="hidden shrink-0 items-center gap-1.5 rounded-md border px-2 py-1 text-xs lg:flex">
      <BookIcon className="size-3.5 shrink-0" />
      <span className="whitespace-nowrap">
        {shortName} · {status.available ? `${status.indexed_books ?? 0} books` : "Unavailable"}
      </span>
      {status.collection && (
        <span className="whitespace-nowrap rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          {status.collection}
        </span>
      )}
      {status.available && status.healthy === false && (
        <span className="whitespace-nowrap text-amber-600">Degraded</span>
      )}
      {syncLabel && (
        <span className="whitespace-nowrap text-muted-foreground">{syncLabel}</span>
      )}
      <Button
        size="sm"
        variant="ghost"
        className="h-6 shrink-0 px-1.5"
        onClick={() => void sync()}
        disabled={loading}
        title="Sync Calibre library"
      >
        {loading ? (
          <Loader2Icon className="size-3 animate-spin" />
        ) : (
          <RefreshCwIcon className="size-3" />
        )}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="h-6 shrink-0 px-1.5"
        onClick={() => void reindex()}
        disabled={loading}
        title="Full reindex"
      >
        Full
      </Button>
    </div>
  );
}
