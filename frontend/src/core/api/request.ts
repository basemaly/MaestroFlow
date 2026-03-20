import { apiFetch, readApiError } from "@/core/api/fetch";
import { getBackendBaseURL } from "@/core/config";

export async function requestJson<T>(
  path: string,
  init?: RequestInit,
  fallbackMessage = "Request failed",
): Promise<T> {
  const response = await apiFetch(`${getBackendBaseURL()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw await readApiError(response, fallbackMessage);
  }
  return (await response.json()) as T;
}
