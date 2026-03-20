import assert from "node:assert/strict";
import test from "node:test";

const {
  resolveBackendBaseURL,
  resolveLangGraphBaseURL,
} = await import(new URL("./index.ts", import.meta.url).href);

void test("uses nginx proxy on the public local app port", () => {
  const location = {
    hostname: "127.0.0.1",
    port: "2027",
    protocol: "http:",
    origin: "http://127.0.0.1:2027",
  };

  assert.equal(resolveBackendBaseURL(location), "");
  assert.equal(resolveLangGraphBaseURL(location, false), "http://127.0.0.1:2027/api/langgraph");
});

void test("targets the direct gateway and langgraph ports from frontend-only local dev", () => {
  const location = {
    hostname: "127.0.0.1",
    port: "3010",
    protocol: "http:",
    origin: "http://127.0.0.1:3010",
  };

  assert.equal(resolveBackendBaseURL(location), "http://127.0.0.1:8001");
  assert.equal(resolveLangGraphBaseURL(location, false), "http://127.0.0.1:2024");
});

void test("keeps mock langgraph traffic on the current frontend origin", () => {
  const location = {
    hostname: "localhost",
    port: "3010",
    protocol: "http:",
    origin: "http://localhost:3010",
  };

  assert.equal(resolveLangGraphBaseURL(location, true), "http://localhost:3010/mock/api");
});

void test("avoids local port rewriting for non-local hosts", () => {
  const location = {
    hostname: "demo.example.com",
    port: "443",
    protocol: "https:",
    origin: "https://demo.example.com",
  };

  assert.equal(resolveBackendBaseURL(location), null);
  assert.equal(resolveLangGraphBaseURL(location, false), "https://demo.example.com/api/langgraph");
});
