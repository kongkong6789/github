export type LightRAGStatus = {
  status: "success" | "unavailable";
  apiUrl: string;
  status_counts: {
    processed: number;
    pending: number;
    processing: number;
    failed: number;
    all: number;
  };
  processed: number;
  pending: number;
  processing: number;
  failed: number;
  pipeline_busy: boolean;
  root_causes: string[];
  checked_at: string;
  timeout_ms?: number;
  error?: string;
};

type LightRAGHealth = {
  pipeline_busy?: boolean;
};

const DEFAULT_TIMEOUT_MS = 3500;

function safeNumber(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function normalizeCounts(value: unknown) {
  const record = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const counts = {
    processed: safeNumber(record.processed ?? record.done ?? record.finished),
    pending: safeNumber(record.pending ?? record.queued),
    processing: safeNumber(record.processing ?? record.running),
    failed: safeNumber(record.failed ?? record.error),
    all: safeNumber(record.all ?? record.total),
  };
  if (!counts.all) {
    counts.all = counts.processed + counts.pending + counts.processing + counts.failed;
  }
  return counts;
}

function rootCausesFromError(error: string): string[] {
  const lower = error.toLowerCase();
  const causes: string[] = [];
  if (lower.includes("timeout") || lower.includes("abort")) causes.push("timeout");
  if (lower.includes("econnrefused") || lower.includes("fetch failed")) {
    causes.push("server_unreachable");
  }
  if (lower.includes("insufficient") || lower.includes("402")) {
    causes.push("quota_or_balance");
  }
  if (lower.includes("500")) causes.push("server_error");
  return causes.length ? causes : ["unknown"];
}

async function fetchWithTimeout(
  url: string,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      cache: "no-store",
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

export async function loadLightRAGStatus({
  apiUrl = (process.env.LIGHTRAG_API_URL ?? "http://127.0.0.1:9621").replace(/\/$/, ""),
  timeoutMs = Number(process.env.LIGHTRAG_STATUS_TIMEOUT_MS ?? DEFAULT_TIMEOUT_MS),
}: {
  apiUrl?: string;
  timeoutMs?: number;
} = {}): Promise<LightRAGStatus> {
  const checkedAt = new Date().toISOString();
  try {
    const [countsResponse, healthResponse] = await Promise.all([
      fetchWithTimeout(`${apiUrl}/documents/status_counts`, timeoutMs),
      fetchWithTimeout(`${apiUrl}/health`, timeoutMs).catch(() => null),
    ]);

    if (!countsResponse.ok) {
      const error = `LightRAG status returned ${countsResponse.status}`;
      const counts = normalizeCounts({});
      return {
        status: "unavailable",
        apiUrl,
        status_counts: counts,
        ...counts,
        pipeline_busy: false,
        root_causes: rootCausesFromError(error),
        checked_at: checkedAt,
        timeout_ms: timeoutMs,
        error,
      };
    }

    const countsPayload = await countsResponse.json();
    const health = healthResponse?.ok
      ? ((await healthResponse.json()) as LightRAGHealth)
      : {};
    const counts = normalizeCounts(
      (countsPayload && typeof countsPayload === "object"
        ? (countsPayload as Record<string, unknown>).status_counts
        : null) ?? countsPayload,
    );

    return {
      status: "success",
      apiUrl,
      status_counts: counts,
      ...counts,
      pipeline_busy: Boolean(health.pipeline_busy),
      root_causes: counts.failed > 0 ? ["document_failures"] : [],
      checked_at: checkedAt,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const counts = normalizeCounts({});
    return {
      status: "unavailable",
      apiUrl,
      status_counts: counts,
      ...counts,
      pipeline_busy: false,
      root_causes: rootCausesFromError(message),
      checked_at: checkedAt,
      timeout_ms: timeoutMs,
      error: message,
    };
  }
}
