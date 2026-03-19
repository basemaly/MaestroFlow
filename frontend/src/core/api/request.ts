import { getBackendBaseURL } from "@/core/config";

export async function requestJson<T>(
  path: string,
  init?: RequestInit,
  fallbackMessage = "Request failed",
): Promise<T> {
  const response = await fetch(`${getBackendBaseURL()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await readError(response, fallbackMessage));
  }
  return (await response.json()) as T;
}

export async function readError(response: Response, fallbackMessage: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string };
    return payload.detail ?? payload.message ?? fallbackMessage;
  } catch {
    const text = await response.text().catch(() => "");
    return text || fallbackMessage;
  }
}
