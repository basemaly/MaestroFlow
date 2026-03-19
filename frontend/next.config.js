/**
 * Run `build` or `dev` with `SKIP_ENV_VALIDATION` to skip env validation. This is especially useful
 * for Docker builds.
 */
import "./src/env.js";

/** @type {import("next").NextConfig} */
const config = {
  allowedDevOrigins: ["127.0.0.1", "localhost", "127.0.0.1:2027", "localhost:2027"],
  devIndicators: false,
  output: "standalone",
};

export default config;
