import { betterAuth } from "better-auth";

export const auth = betterAuth({
  baseURL: process.env.BETTER_AUTH_BASE_URL
    ?? process.env.MAESTROFLOW_PUBLIC_ORIGIN
    ?? "http://localhost:2027",
  emailAndPassword: {
    enabled: true,
  },
});

export type Session = typeof auth.$Infer.Session;
