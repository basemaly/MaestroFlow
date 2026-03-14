"use client";

function extractDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  if ("detail" in payload && typeof payload.detail === "string") {
    return payload.detail;
  }
  if ("message" in payload && typeof payload.message === "string") {
    return payload.message;
  }
  return null;
}

export function normalizeThreadError(error: unknown): string {
  if (error instanceof Error) {
    const raw = error.message.trim();
    if (!raw) {
      return "MaestroFlow could not complete that request.";
    }

    if (/invalid thread id/i.test(raw)) {
      return "That chat thread is no longer valid. Start a new thread and try again.";
    }
    if (/Failed to fetch/i.test(raw) || /fetch failed/i.test(raw)) {
      return "MaestroFlow could not reach its backend services. Check that the app stack is running and try again.";
    }
    if (/ECONNREFUSED|connection refused|connect error|network error/i.test(raw)) {
      return "A required external service is offline or unreachable. Check the warning banner above and try again.";
    }
    if (/status code 5\d\d/i.test(raw) || /^HTTP 5\d\d/i.test(raw)) {
      return "MaestroFlow hit a backend service error. Check the warning banner above and try again.";
    }
    return raw;
  }

  const detail = extractDetail(error);
  if (detail) {
    return normalizeThreadError(new Error(detail));
  }

  return "MaestroFlow could not complete that request.";
}
