import { headers } from "next/headers";

import { env } from "@/env";

export async function getServerAppOrigin(): Promise<string> {
  if (env.NEXT_PUBLIC_BACKEND_BASE_URL) {
    return env.NEXT_PUBLIC_BACKEND_BASE_URL;
  }

  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host");
  const proto = requestHeaders.get("x-forwarded-proto") ?? "http";

  if (!host) {
    return "http://localhost:2027";
  }

  return `${proto}://${host}`;
}
