import { NextResponse } from "next/server";

import { checkWorkbenchAuth } from "./api-auth";

type RouteAuthOptions = {
  protectRead?: boolean;
};

export function workbenchAuthResponse(
  request: {
    method: string;
    url?: string;
    headers: { get(name: string): string | null };
  },
  options: RouteAuthOptions = {},
) {
  const auth = checkWorkbenchAuth(request, options);
  if (auth.ok) return null;
  return NextResponse.json(
    {
      ok: false,
      status: "error",
      code: "unauthorized",
      error: auth.error,
      message: auth.error,
    },
    { status: auth.status },
  );
}
