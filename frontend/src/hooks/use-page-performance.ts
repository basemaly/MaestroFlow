"use client";

import { useEffect, useState } from "react";

export interface PagePerformanceMetrics {
  domContentLoaded: number;
  pageLoadTime: number;
  navigationStart: number;
  firstPaint?: number;
  firstContentfulPaint?: number;
}

export function usePagePerformance() {
  const [metrics, setMetrics] = useState<PagePerformanceMetrics | null>(null);

  useEffect(() => {
    // Use PerformanceObserver for modern browsers
    if (typeof window !== "undefined" && "PerformanceObserver" in window) {
      try {
        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          for (const entry of entries) {
            if (entry.name === "first-paint") {
              setMetrics((prev) =>
                prev ? { ...prev, firstPaint: Math.round(entry.startTime) } : null,
              );
            }
            if (entry.name === "first-contentful-paint") {
              setMetrics((prev) =>
                prev ? { ...prev, firstContentfulPaint: Math.round(entry.startTime) } : null,
              );
            }
          }
        });

        observer.observe({ entryTypes: ["paint"] });

        // Fallback to timing API
        const onLoad = () => {
          const timing = performance.timing;
          const navigationStart = timing.navigationStart;

          setMetrics({
            navigationStart,
            domContentLoaded: timing.domContentLoadedEventEnd - navigationStart,
            pageLoadTime: timing.loadEventEnd - navigationStart,
          });
        };

        window.addEventListener("load", onLoad);
        return () => {
          window.removeEventListener("load", onLoad);
          observer.disconnect();
        };
      } catch {
        // Silently fail if performance API is not available
      }
    }
  }, []);

  return metrics;
}
