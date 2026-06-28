import { initApiPassthrough } from "langgraph-nextjs-api-passthrough";
import type { NextRequest, NextResponse } from "next/server";

import { workbenchAuthResponse } from "@/lib/api-route-auth";

// This file acts as a proxy for requests to your LangGraph server.
// Read the [Going to Production](https://github.com/langchain-ai/agent-chat-ui?tab=readme-ov-file#going-to-production) section for more information.

const passthrough = initApiPassthrough({
  apiUrl: process.env.LANGGRAPH_API_URL ?? "remove-me", // default, if not defined it will attempt to read process.env.LANGGRAPH_API_URL
  apiKey: process.env.LANGSMITH_API_KEY ?? "remove-me", // default, if not defined it will attempt to read process.env.LANGSMITH_API_KEY
  runtime: "edge", // default
});

function protectProxy(
  handler: (request: NextRequest) => Promise<NextResponse<unknown>>,
) {
  return (request: NextRequest) => {
    const authResponse = workbenchAuthResponse(request, { protectRead: true });
    if (authResponse) return authResponse;
    return handler(request);
  };
}

export const GET = protectProxy(passthrough.GET);
export const POST = protectProxy(passthrough.POST);
export const PUT = protectProxy(passthrough.PUT);
export const PATCH = protectProxy(passthrough.PATCH);
export const DELETE = protectProxy(passthrough.DELETE);
export const OPTIONS = (request: NextRequest) => {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  return passthrough.OPTIONS();
};
export const runtime = "edge";
