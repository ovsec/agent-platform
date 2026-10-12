import { NextResponse, type NextRequest } from "next/server";

// Sign-in only works on the public URL (AUTH_URL): the IdP sends the browser back there, and its login cookies
// must be on the same host. When the portal is shared (scripts/share.sh, AUTH_URL = the Tailscale HTTPS address),
// a browser on another address, e.g. http://localhost:3100, is sent to the public one.
export function middleware(req: NextRequest) {
  const publicUrl = process.env.AUTH_URL;
  if (!publicUrl) return NextResponse.next();
  const target = new URL(publicUrl);
  if (req.headers.get("host") === target.host) return NextResponse.next();
  const url = new URL(req.nextUrl.pathname + req.nextUrl.search, target);
  return NextResponse.redirect(url, 307);
}

export const config = {
  matcher: ["/((?!_next/|favicon.ico).*)"],
};
