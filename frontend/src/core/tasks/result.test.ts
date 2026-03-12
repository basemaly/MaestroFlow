import assert from "node:assert/strict";
import test from "node:test";

const { parseTaskToolResult } = await import(
  new URL("./result.ts", import.meta.url).href
);

void test("parses structured task metadata blocks", () => {
  const parsed = parseTaskToolResult(
    '<task-metadata>{"status":"completed","subagent_type":"writing-refiner","result":"Rewritten text","artifact":{"schema":"editorial-rewrite"},"quality":{"composite":0.82}}</task-metadata>\n\nTask status: completed'
  );

  assert.ok(parsed);
  assert.equal(parsed?.status, "completed");
  assert.equal(parsed?.subagent_type, "writing-refiner");
  assert.equal(parsed?.artifact?.schema, "editorial-rewrite");
  assert.equal(parsed?.quality?.composite, 0.82);
});

void test("returns null when no metadata block exists", () => {
  assert.equal(parseTaskToolResult("plain tool output"), null);
});
