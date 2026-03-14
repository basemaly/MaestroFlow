"use client";

import { AlertTriangleIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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

export function ExternalServiceBanner() {
  const [payload, setPayload] = useState<ExternalServicesPayload | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch(`${getBackendBaseURL()}/api/health/external-services`);
        if (!response.ok) {
          if (!cancelled) {
            setPayload(FALLBACK_WARNING);
          }
          return;
        }
        const data = (await response.json()) as ExternalServicesPayload;
        if (!cancelled) {
          setPayload(data);
        }
      } catch {
        if (!cancelled) {
          setPayload(FALLBACK_WARNING);
        }
      }
    }

    void load();
    const intervalId = window.setInterval(() => {
      void load();
    }, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, []);

  const warnings = (payload?.services ?? []).filter(
    (service) => !service.available && (service.configured || service.required),
  );
  if (!warnings.length) {
    return null;
  }

  return (
    <Alert className="mx-auto mt-14 mb-2 max-w-(--container-width-md) border-amber-500/30 bg-amber-500/8 text-amber-950 dark:text-amber-100">
      <AlertTriangleIcon className="size-4" />
      <AlertTitle>Some external services are unavailable</AlertTitle>
      <AlertDescription>
        {warnings.map((service) => `${service.label}: ${service.message ?? "Unavailable"}`).join(" ")}
      </AlertDescription>
    </Alert>
  );
}
