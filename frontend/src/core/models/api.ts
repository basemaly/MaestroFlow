import { apiFetch } from "../api/fetch";
import { getBackendBaseURL } from "../config";

import type { Model } from "./types";

export async function loadModels() {
  const res = await apiFetch(`${getBackendBaseURL()}/api/models`);
  const { models } = (await res.json()) as { models: Model[] };
  return models;
}
