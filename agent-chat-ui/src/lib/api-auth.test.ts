import assert from "node:assert/strict";
import { test } from "node:test";

import {
  checkWorkbenchAuth,
  extractApiKey,
  isTrustedLocalRequest,
  isMutatingMethod,
} from "./api-auth";

function mockRequest(
  method: string,
  headers: Record<string, string> = {},
  url = "http://localhost:3000/api/workbench",
) {
  return {
    method,
    url,
    headers: {
      get(name: string): string | null {
        return headers[name.toLowerCase()] ?? (name.toLowerCase() === "host" ? "localhost:3000" : null);
      },
    },
  };
}

function setTestEnv(name: string, value: string | undefined) {
  const writableEnv = process.env as Record<string, string | undefined>;
  if (value === undefined) {
    delete writableEnv[name];
  } else {
    writableEnv[name] = value;
  }
}

test("GET requests always pass auth", () => {
  const result = checkWorkbenchAuth(mockRequest("GET"));
  assert.equal(result.ok, true);
});

test("HEAD and OPTIONS requests always pass auth", () => {
  assert.equal(checkWorkbenchAuth(mockRequest("HEAD")).ok, true);
  assert.equal(checkWorkbenchAuth(mockRequest("OPTIONS")).ok, true);
});

test("protected read requests pass only for trusted localhost without key", () => {
  const original = process.env.A2A_WORKBENCH_API_KEY;
  const originalNodeEnv = process.env.NODE_ENV;
  try {
    setTestEnv("A2A_WORKBENCH_API_KEY", undefined);
    setTestEnv("NODE_ENV", "development");

    assert.equal(
      checkWorkbenchAuth(
        mockRequest("GET", {
          host: "localhost:3000",
          origin: "http://localhost:3000",
        }),
        { protectRead: true },
      ).ok,
      true,
    );

    const crossOrigin = checkWorkbenchAuth(
      mockRequest("GET", {
        host: "localhost:3000",
        origin: "https://evil.example",
      }),
      { protectRead: true },
    );
    assert.equal(crossOrigin.ok, false);
    if (!crossOrigin.ok) assert.equal(crossOrigin.status, 503);
  } finally {
    setTestEnv("A2A_WORKBENCH_API_KEY", original);
    setTestEnv("NODE_ENV", originalNodeEnv);
  }
});

test("isMutatingMethod identifies POST/PATCH/PUT/DELETE", () => {
  assert.equal(isMutatingMethod("POST"), true);
  assert.equal(isMutatingMethod("PATCH"), true);
  assert.equal(isMutatingMethod("PUT"), true);
  assert.equal(isMutatingMethod("DELETE"), true);
  assert.equal(isMutatingMethod("GET"), false);
  assert.equal(isMutatingMethod("HEAD"), false);
});

test("extractApiKey reads x-a2a-api-key header", () => {
  const key = extractApiKey(
    mockRequest("POST", { "x-a2a-api-key": "test-key-123" }),
  );
  assert.equal(key, "test-key-123");
});

test("extractApiKey reads Bearer token from authorization header", () => {
  const key = extractApiKey(
    mockRequest("POST", { authorization: "Bearer my-secret-token" }),
  );
  assert.equal(key, "my-secret-token");
});

test("extractApiKey prefers x-a2a-api-key over Bearer", () => {
  const key = extractApiKey(
    mockRequest("POST", {
      "x-a2a-api-key": "header-key",
      authorization: "Bearer bearer-key",
    }),
  );
  assert.equal(key, "header-key");
});

test("mutating localhost request without A2A_WORKBENCH_API_KEY in dev passes", () => {
  const original = process.env.A2A_WORKBENCH_API_KEY;
  const originalNodeEnv = process.env.NODE_ENV;
  try {
    setTestEnv("A2A_WORKBENCH_API_KEY", undefined);
    setTestEnv("NODE_ENV", "development");
    const result = checkWorkbenchAuth(mockRequest("POST"));
    assert.equal(result.ok, true);
  } finally {
    setTestEnv("A2A_WORKBENCH_API_KEY", original);
    setTestEnv("NODE_ENV", originalNodeEnv);
  }
});

test("mutating non-local request without A2A_WORKBENCH_API_KEY in dev rejects", () => {
  const original = process.env.A2A_WORKBENCH_API_KEY;
  const originalNodeEnv = process.env.NODE_ENV;
  try {
    setTestEnv("A2A_WORKBENCH_API_KEY", undefined);
    setTestEnv("NODE_ENV", "development");
    const result = checkWorkbenchAuth(
      mockRequest(
        "POST",
        { host: "192.168.1.20:3000" },
        "http://192.168.1.20:3000/api/workbench",
      ),
    );
    assert.equal(result.ok, false);
    if (!result.ok) assert.equal(result.status, 503);
  } finally {
    setTestEnv("A2A_WORKBENCH_API_KEY", original);
    setTestEnv("NODE_ENV", originalNodeEnv);
  }
});

test("mutating request without A2A_WORKBENCH_API_KEY in production rejects", () => {
  const original = process.env.A2A_WORKBENCH_API_KEY;
  const originalNodeEnv = process.env.NODE_ENV;
  try {
    setTestEnv("A2A_WORKBENCH_API_KEY", undefined);
    setTestEnv("NODE_ENV", "production");
    const result = checkWorkbenchAuth(mockRequest("POST"));
    assert.equal(result.ok, false);
    if (!result.ok) {
      assert.equal(result.status, 503);
    }
  } finally {
    setTestEnv("A2A_WORKBENCH_API_KEY", original);
    setTestEnv("NODE_ENV", originalNodeEnv);
  }
});

test("mutating request with configured x-a2a-api-key passes", () => {
  const original = process.env.A2A_WORKBENCH_API_KEY;
  try {
    setTestEnv("A2A_WORKBENCH_API_KEY", "expected-key");
    const result = checkWorkbenchAuth(
      mockRequest(
        "DELETE",
        { "x-a2a-api-key": "expected-key", host: "192.168.1.20:3000" },
        "http://192.168.1.20:3000/api/workbench",
      ),
    );
    assert.equal(result.ok, true);
  } finally {
    setTestEnv("A2A_WORKBENCH_API_KEY", original);
  }
});

test("mutating request with wrong configured key rejects", () => {
  const original = process.env.A2A_WORKBENCH_API_KEY;
  try {
    setTestEnv("A2A_WORKBENCH_API_KEY", "expected-key");
    const result = checkWorkbenchAuth(
      mockRequest(
        "PATCH",
        { authorization: "Bearer wrong-key", host: "192.168.1.20:3000" },
        "http://192.168.1.20:3000/api/workbench",
      ),
    );
    assert.equal(result.ok, false);
    if (!result.ok) {
      assert.equal(result.status, 403);
    }
  } finally {
    setTestEnv("A2A_WORKBENCH_API_KEY", original);
  }
});

test("trusted local request rejects mismatched browser origin", () => {
  assert.equal(
    isTrustedLocalRequest(
      mockRequest("POST", {
        host: "127.0.0.1:3000",
        origin: "https://attacker.example",
      }),
    ),
    false,
  );
});
