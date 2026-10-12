import NextAuth, { customFetch } from "next-auth";
import type { JWT } from "next-auth/jwt";

// Generic OAuth2/OIDC: any provider with discovery works (Keycloak locally, Entra ID, Okta, ...).
// The access token is what the gateway checks: it must carry aud=agent-platform, sub and a `roles` array.
const issuer = process.env.OIDC_ISSUER!;
const clientId = process.env.OIDC_CLIENT_ID!;
const clientSecret = process.env.OIDC_CLIENT_SECRET!;
const scope = process.env.OIDC_SCOPE ?? "openid";
// Optional: where this server reaches the IdP when the public issuer URL is not reachable from here (e.g. in
// Docker: issuer http://localhost:8180/realms/agents, internal http://keycloak:8080/realms/agents). Server-side
// requests to the issuer are rewritten; the browser and the token's `iss` keep using the public issuer.
const internalIssuer = process.env.OIDC_INTERNAL_ISSUER;

function idpFetch(input: string | URL | Request, init?: RequestInit): Promise<Response> {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  if (internalIssuer && url.startsWith(issuer)) {
    return fetch(internalIssuer + url.slice(issuer.length), init);
  }
  return fetch(input, init);
}

declare module "next-auth" {
  interface Session {
    roles: string[];
    error?: "RefreshTokenError";
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken?: string;
    refreshToken?: string;
    expiresAt?: number; // epoch seconds
    roles?: string[];
    error?: "RefreshTokenError";
  }
}

/** Claims of a JWT without verifying it: display and UI gating only, the gateway does the real check. */
export function decodeClaims(token: string): Record<string, unknown> {
  return JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString("utf8"));
}

function rolesFrom(accessToken: string | undefined): string[] {
  const roles = accessToken ? decodeClaims(accessToken).roles : undefined;
  return Array.isArray(roles) ? roles.filter((r): r is string => typeof r === "string") : [];
}

let tokenEndpoint: string | undefined;
async function getTokenEndpoint(): Promise<string> {
  if (!tokenEndpoint) {
    const res = await idpFetch(`${issuer}/.well-known/openid-configuration`);
    tokenEndpoint = (await res.json()).token_endpoint as string;
  }
  return tokenEndpoint;
}

async function refresh(token: JWT): Promise<JWT> {
  if (!token.refreshToken) return { ...token, error: "RefreshTokenError" };
  const res = await idpFetch(await getTokenEndpoint(), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: token.refreshToken,
      client_id: clientId,
      client_secret: clientSecret,
    }),
  });
  const body = await res.json();
  if (!res.ok) return { ...token, error: "RefreshTokenError" };
  return {
    ...token,
    accessToken: body.access_token,
    refreshToken: body.refresh_token ?? token.refreshToken,
    expiresAt: Math.floor(Date.now() / 1000) + body.expires_in,
    roles: rolesFrom(body.access_token),
    error: undefined,
  };
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    {
      id: "oidc",
      name: process.env.OIDC_DISPLAY_NAME ?? "Single sign-on",
      type: "oidc",
      issuer,
      clientId,
      clientSecret,
      authorization: { params: { scope } },
      [customFetch]: idpFetch,
    },
  ],
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        return {
          ...token,
          accessToken: account.access_token,
          refreshToken: account.refresh_token,
          expiresAt: account.expires_at,
          roles: rolesFrom(account.access_token),
        };
      }
      if (token.expiresAt && Date.now() < (token.expiresAt - 60) * 1000) return token;
      return refresh(token);
    },
    // Only roles and the error flag reach the browser; tokens stay in the encrypted session cookie.
    async session({ session, token }) {
      session.roles = token.roles ?? [];
      session.error = token.error;
      return session;
    },
  },
});

/** The signed-in session, or null when signed out or the IdP refused to refresh the tokens (sign in again). */
export async function currentSession() {
  const session = await auth();
  return session && !session.error ? session : null;
}
