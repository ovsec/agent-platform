import { getToken } from "next-auth/jwt";
import type { NextRequest } from "next/server";

// Pass-through to the gateway: adds the user's access token (kept server side) and streams the AG-UI
// SSE response back unchanged. Nothing here is runtime-specific; the gateway owns routing and auth.
const GATEWAY_URL = process.env.GATEWAY_URL ?? "http://localhost:4100";

export async function POST(req: NextRequest, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!/^[a-z0-9-]+$/.test(slug)) return new Response("unknown agent", { status: 404 });

  // Read the session cookie under the name sign-in used: behind an HTTPS proxy that forwards plain HTTP (tailscale
  // serve) Auth.js sets the non-secure name although AUTH_URL is https, and getToken would look for __Secure-.
  const secureCookie = req.cookies.has("__Secure-authjs.session-token");
  const token = await getToken({ req, secret: process.env.AUTH_SECRET, secureCookie });
  if (!token?.accessToken || token.error) return new Response("not signed in", { status: 401 });

  const body = await req.text();
  let threadId = "";
  try {
    threadId = String(JSON.parse(body).threadId ?? "");
  } catch {
    return new Response("invalid AG-UI request", { status: 400 });
  }

  const upstream = await fetch(`${GATEWAY_URL}/agents/${slug}/run`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token.accessToken}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "x-agui-thread-id": threadId, // audit: lets the gateway log line be joined to the conversation
    },
    body,
    signal: req.signal, // user pressed stop → cancel the run upstream
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
    },
  });
}
