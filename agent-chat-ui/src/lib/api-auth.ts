function extractBearerToken(authorization: string | null): string {
  if (!authorization) return "";
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  return match ? match[1].trim() : "";
}

type HeaderReader = { get(name: string): string | null };

type AuthRequest = {
  method: string;
  url?: string;
  headers: HeaderReader;
};

type AuthOptions = {
  protectRead?: boolean;
};

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

export function extractApiKey(request: {
  headers: HeaderReader;
}): string {
  return (
    request.headers.get("x-a2a-api-key")?.trim() ||
    extractBearerToken(request.headers.get("authorization")) ||
    ""
  );
}

export function isMutatingMethod(method: string): boolean {
  const upper = method.toUpperCase();
  return upper === "POST" || upper === "PATCH" || upper === "PUT" || upper === "DELETE";
}

function configuredWorkbenchApiKey(): string {
  return process.env.A2A_WORKBENCH_API_KEY?.trim() || "";
}

function normalizeHost(value: string): string {
  const raw = value.trim().toLowerCase();
  if (!raw) return "";
  if (raw.startsWith("[") && raw.includes("]")) {
    return raw.slice(1, raw.indexOf("]"));
  }
  return raw.split(":")[0] ?? "";
}

function hostFromRequest(request: AuthRequest): string {
  return normalizeHost(
    request.headers.get("x-forwarded-host") ||
      request.headers.get("host") ||
      (request.url ? new URL(request.url).host : ""),
  );
}

function isLoopbackHost(host: string): boolean {
  return LOOPBACK_HOSTS.has(host) || host.startsWith("127.");
}

function originMatchesHost(origin: string, host: string): boolean {
  try {
    return normalizeHost(new URL(origin).host) === host;
  } catch {
    return false;
  }
}

export function isTrustedLocalRequest(request: AuthRequest): boolean {
  const host = hostFromRequest(request);
  if (!isLoopbackHost(host)) return false;
  const origin = request.headers.get("origin");
  return !origin || originMatchesHost(origin, host);
}

function requiresApiKey(request: AuthRequest): boolean {
  if (process.env.NODE_ENV === "production") return true;
  if (process.env.A2A_WORKBENCH_REQUIRE_API_KEY === "true") return true;
  return !isTrustedLocalRequest(request);
}

export function checkWorkbenchAuth(
  request: AuthRequest,
  options: AuthOptions = {},
): { ok: true } | { ok: false; error: string; status: number } {
  const protectedMethod = isMutatingMethod(request.method);
  if (!protectedMethod && !options.protectRead) {
    return { ok: true };
  }

  if (!requiresApiKey(request)) {
    return { ok: true };
  }

  const workbenchApiKey = configuredWorkbenchApiKey();
  if (!workbenchApiKey) {
    return {
      ok: false,
      error:
        "服务端未配置 A2A_WORKBENCH_API_KEY，当前请求不是可信本机同源访问，已禁止访问工作台敏感接口。",
      status: 503,
    };
  }

  const provided = extractApiKey(request);
  if (!provided) {
    return {
      ok: false,
      error: "缺少 API 密钥。请在请求头中设置 x-a2a-api-key 或 Authorization: Bearer <key>。",
      status: 401,
    };
  }
  if (provided !== workbenchApiKey) {
    return {
      ok: false,
      error: "API 密钥无效。",
      status: 403,
    };
  }
  return { ok: true };
}
