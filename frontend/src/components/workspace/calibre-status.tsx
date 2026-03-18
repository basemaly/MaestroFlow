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
  indexed_books?: number;
  indexed_chunks?: number;
  last_sync_at?: string | null;
  last_error?: string | null;
};

export function CalibreStatus() {
  const [status, setStatus] = useState<CalibreStatusPayload | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const response = await fetch(`${getBackendBaseURL()}/api/calibre/status`);
      const payload = (await response.json()) as CalibreStatusPayload;
      setStatus(payload);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
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
      const payload = (await response.json()) as CalibreStatusPayload;
      setStatus(payload);
      if (payload.last_error) {
        toast.error(payload.last_error);
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
      const payload = (await response.json()) as CalibreStatusPayload;
      setStatus(payload);
      if (payload.last_error) {
        toast.error(payload.last_error);
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
