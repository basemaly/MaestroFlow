"use client";

import { AlertTriangleIcon, RefreshCwIcon, XIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { getBackendBaseURL } from "@/core/config";

type ExternalService = {
  service: string;
  label: string;
  configured: boolean;
  available: boolean;
  required: boolean;
  message?: string | null;
};

type ExternalServicesPayload = {
  services: ExternalService[];
  degraded: boolean;
};

const FALLBACK_WARNING: ExternalServicesPayload = {
  degraded: true,
  services: [
    {
      service: "gateway-health",
      label: "Gateway",
      configured: true,
      available: false,
      required: true,
      message:
        "Service status could not be checked. The backend may still be starting or temporarily unavailable.",
    },
  ],
};

const POLL_INTERVAL_MS = 30_000;

export function ExternalServiceBanner() {
  const [payload, setPayload] = useState<ExternalServicesPayload | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const cancelledRef = useRef(false);

  const load = useCallback(async () => {
    try {
      const response = await fetch(`${getBackendBaseURL()}/api/health/external-services`);
      if (!response.ok) {
        if (!cancelledRef.current) setPayload(FALLBACK_WARNING);
        return;
      }
      const data = (await response.json()) as ExternalServicesPayload;
      if (!cancelledRef.current) {
        setPayload(data);
        // Auto-clear dismiss if services recovered
        if (!data.degraded) setDismissed(false);
      }
    } catch {
      if (!cancelledRef.current) setPayload(FALLBACK_WARNING);
    }
  }, []);

  useEffect(() => {
    cancelledRef.current = false;
    void load();
    const intervalId = window.setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => {
      cancelledRef.current = true;
      window.clearInterval(intervalId);
    };
  }, [load]);

  const handleRetry = useCallback(async () => {
    setRefreshing(true);
    setDismissed(false);
    await load();
    setRefreshing(false);
  }, [load]);

  const warnings = (payload?.services ?? []).filter(
    (service) => !service.available && (service.configured || service.required),
  );

  if (!warnings.length || dismissed) {
    return null;
  }

  const failedNames = warnings.map((s) => s.label).join(", ");

  return (
    <Alert className="mx-auto mt-14 mb-2 max-w-(--container-width-md) border-amber-500/30 bg-amber-500/8 text-amber-950 dark:text-amber-100">
      <AlertTriangleIcon className="size-4" />
      <AlertTitle className="flex items-center justify-between gap-2">
        <span>
          {failedNames} {warnings.length === 1 ? "is" : "are"} unavailable
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="size-6 text-amber-700 hover:bg-amber-500/15 hover:text-amber-900 dark:text-amber-300 dark:hover:text-amber-100"
            onClick={handleRetry}
            disabled={refreshing}
            title="Check again"
          >
            <RefreshCwIcon className={`size-3 ${refreshing ? "animate-spin" : ""}`} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-6 text-amber-700 hover:bg-amber-500/15 hover:text-amber-900 dark:text-amber-300 dark:hover:text-amber-100"
            onClick={() => setDismissed(true)}
            title="Dismiss"
          >
            <XIcon className="size-3" />
          </Button>
        </div>
      </AlertTitle>
      <AlertDescription>
        <ul className="mt-1 list-disc pl-4 text-sm">
          {warnings.map((service) => (
            <li key={service.service}>
              <span className="font-medium">{service.label}:</span>{" "}
              {service.message ?? "Unavailable"}
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}
