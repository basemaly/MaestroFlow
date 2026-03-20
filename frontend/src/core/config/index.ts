import { env } from "@/env";

const LOCAL_DEV_HOSTS = new Set(["localhost", "127.0.0.1"]);
const PUBLIC_PROXY_PORTS = new Set(["2027"]);
const FRONTEND_ONLY_PORTS = new Set(["3000", "3010"]);

type BrowserLocationLike = {
  hostname: string;
  port?: string;
  protocol: string;
  origin: string;
};

function normalizeHost(hostname: string) {
  return hostname.trim().toLowerCase();
}

function getBrowserLocation(location?: BrowserLocationLike | null) {
  if (location) {
    return location;
  }

  if (typeof window === "undefined") {
    return null;
  }

  return window.location;
}

export function resolveBackendBaseURL(location?: BrowserLocationLike | null) {
  const browserLocation = getBrowserLocation(location);
  if (!browserLocation) {
    return null;
  }

  const host = normalizeHost(browserLocation.hostname);
  const port = browserLocation.port ?? (browserLocation.protocol === "https:" ? "443" : "80");

  if (!LOCAL_DEV_HOSTS.has(host)) {
    return null;
  }

  if (PUBLIC_PROXY_PORTS.has(port)) {
    return "";
  }

  if (FRONTEND_ONLY_PORTS.has(port)) {
    return `${browserLocation.protocol}//${host}:8001`;
  }

  return `${browserLocation.protocol}//${host}:8001`;
}

export function getBackendBaseURL() {
  if (env.NEXT_PUBLIC_BACKEND_BASE_URL) {
    return env.NEXT_PUBLIC_BACKEND_BASE_URL;
  }

  return resolveBackendBaseURL() ?? "";
}

export function resolveLangGraphBaseURL(location?: BrowserLocationLike | null, isMock?: boolean) {
  const browserLocation = getBrowserLocation(location);
  if (!browserLocation) {
    return isMock ? "http://localhost:3000/mock/api" : "http://localhost:2027/api/langgraph";
  }

  const host = normalizeHost(browserLocation.hostname);
  const port = browserLocation.port ?? (browserLocation.protocol === "https:" ? "443" : "80");

  if (isMock) {
    return `${browserLocation.origin}/mock/api`;
  }

  if (LOCAL_DEV_HOSTS.has(host) && FRONTEND_ONLY_PORTS.has(port)) {
    return `${browserLocation.protocol}//${host}:2024`;
  }

  return `${browserLocation.origin}/api/langgraph`;
}

export function getLangGraphBaseURL(isMock?: boolean) {
  if (env.NEXT_PUBLIC_LANGGRAPH_BASE_URL) {
    return env.NEXT_PUBLIC_LANGGRAPH_BASE_URL;
  } else if (isMock) {
    if (typeof window !== "undefined") {
      return `${window.location.origin}/mock/api`;
    }
    return "http://localhost:3000/mock/api";
  } else {
    return resolveLangGraphBaseURL(undefined, false);
  }
}
