export class ApiError extends Error {
  requestId?: string;
  traceId?: string;
  status?: number;

  constructor(message: string, options?: { requestId?: string | null; traceId?: string | null; status?: number }) {
    super(message);
    this.name = "ApiError";
    this.requestId = options?.requestId ?? undefined;
    this.traceId = options?.traceId ?? undefined;
    this.status = options?.status;
  }
}

export function buildRequestId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `mf-${crypto.randomUUID()}`;
  }
  return `mf-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function buildTraceId(seed?: string) {
  const normalizedSeed = seed?.trim().replace(/[^a-zA-Z0-9:_-]+/g, "-").slice(0, 48);
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return normalizedSeed
      ? `trace-${normalizedSeed}-${crypto.randomUUID()}`
      : `trace-${crypto.randomUUID()}`;
  }
  const randomPart = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  return normalizedSeed ? `trace-${normalizedSeed}-${randomPart}` : `trace-${randomPart}`;
}

export function withRequestIdHeaders(headers?: HeadersInit, traceId?: string): Headers {
  const nextHeaders = new Headers(headers ?? {});
  if (!nextHeaders.has("X-Request-ID")) {
    nextHeaders.set("X-Request-ID", buildRequestId());
  }
  if (traceId && !nextHeaders.has("X-Trace-ID")) {
    nextHeaders.set("X-Trace-ID", traceId);
  }
  return nextHeaders;
}

export async function apiFetch(
  input: string | URL | globalThis.Request,
  init?: RequestInit & { traceId?: string },
): Promise<Response> {
  return fetch(input, {
    ...init,
    headers: withRequestIdHeaders(init?.headers, init?.traceId),
  });
}

function formatRequestMeta(requestId?: string | null, traceId?: string | null): string {
  const meta: string[] = [];
  if (requestId) meta.push(`Request ID: ${requestId}`);
  if (traceId) meta.push(`Trace ID: ${traceId}`);
  return meta.length ? ` [${meta.join(" · ")}]` : "";
}

export async function readApiError(response: Response, fallbackMessage: string): Promise<ApiError> {
  let message = fallbackMessage;
  try {
    const payload = (await response.clone().json()) as { detail?: string; message?: string };
    message = payload.detail ?? payload.message ?? fallbackMessage;
  } catch {
    const text = await response.text().catch(() => "");
    if (text) {
      message = text;
    }
  }

  const requestId = response.headers.get("X-Request-ID");
  const traceId = response.headers.get("X-Trace-ID");
  return new ApiError(`${message}${formatRequestMeta(requestId, traceId)}`, {
    requestId,
    traceId,
    status: response.status,
  });
}

export function formatUnknownError(error: unknown, fallback = "Request failed"): string {
  if (error instanceof Error) {
    return error.message || fallback;
  }
  return typeof error === "string" ? error : fallback;
}
