"use client";

import { BookIcon, Loader2Icon, RefreshCwIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
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
      const response = await fetch(`${getBackendBaseURL()}/api/calibre/status`);
      const payload = await readCalibrePayload(response);
      if (!response.ok || !payload) {
        setStatus(fallbackFromResponse(response, "Calibre status endpoint unavailable"));
        return;
      }
      setStatus({ ...FALLBACK_STATUS, ...payload });
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
      const response = await fetch(`${getBackendBaseURL()}/api/calibre/sync`, {
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
      const response = await fetch(`${getBackendBaseURL()}/api/calibre/reindex`, {
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

  return (
    <div className="hidden items-center gap-2 rounded-md border px-2 py-1 text-xs lg:flex">
      <BookIcon className="size-3.5" />
      <span>
        {status.dataset_name ?? "Calibre Library"} ·{" "}
        {status.available ? `${status.indexed_books ?? 0} books` : "Unavailable"}
      </span>
      {status.collection && (
        <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          {status.collection}
        </span>
      )}
      {status.available && status.healthy === false && (
        <span className="text-amber-600">Degraded</span>
      )}
      {status.last_sync_at && (
        <span className="text-muted-foreground">
          Synced {new Date(status.last_sync_at).toLocaleString()}
        </span>
      )}
      <Button
        size="sm"
        variant="ghost"
        className="h-6 px-1.5"
        onClick={() => void sync()}
        disabled={loading}
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
        className="h-6 px-1.5"
        onClick={() => void reindex()}
        disabled={loading}
      >
        Full
      </Button>
    </div>
  );
}
