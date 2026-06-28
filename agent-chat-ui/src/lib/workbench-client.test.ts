import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { callWorkbench, WorkbenchClientError } from "./workbench-client";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("callWorkbench reports HTML error pages as non-JSON workbench responses", async () => {
  globalThis.fetch = async () =>
    new Response("<!DOCTYPE html><html><body>Internal Server Error</body></html>", {
      status: 500,
      headers: { "content-type": "text/html; charset=utf-8" },
    });

  await assert.rejects(
    () => callWorkbench("agent.trace", { thread_id: "thread-1" }),
    (error) => {
      assert(error instanceof WorkbenchClientError);
      assert.equal(error.code, "workbench_non_json_response");
      assert.equal(error.retryable, true);
      assert.equal(error.source, "workbench_client");
      assert.match(error.message, /非 JSON/);
      assert.deepEqual(
        (error.details as { contentType?: string; status?: number })?.contentType,
        "text/html; charset=utf-8",
      );
      return true;
    },
  );
});
