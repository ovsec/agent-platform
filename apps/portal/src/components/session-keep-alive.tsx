"use client";

import { SessionProvider, useSession } from "next-auth/react";

// Polling the session runs the Auth.js jwt callback, which refreshes the access token before it expires
// (the agent run route reads the cookie and cannot refresh it itself).
export function SessionKeepAlive() {
  return (
    <SessionProvider refetchInterval={120} refetchOnWindowFocus>
      <Poll />
    </SessionProvider>
  );
}

function Poll() {
  useSession();
  return null;
}
