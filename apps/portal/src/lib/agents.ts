import "server-only";

import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { parse } from "yaml";
import type { AgentSummary } from "@/lib/agent-summary";

// The deployed agents: <AGENTS_DIR>/<slug>/agent.yaml (catalog/ locally, agent-catalog/<env>/ elsewhere), the same
// files the gateway routes are generated from. P2 moves the catalog into the portal database.
const AGENTS_DIR =
  process.env.AGENTS_DIR ?? path.resolve(process.cwd(), "../../catalog");

export type Agent = {
  slug: string;
  name: string;
  description: string;
  owner_team: string;
  tags: string[];
  runtime: "langflow" | "agui";
  access: { roles: string[] };
  starter_prompts?: string[];
};

export async function listAgents(): Promise<Agent[]> {
  const dirs = (await readdir(AGENTS_DIR, { withFileTypes: true }))
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .sort();
  const agents = await Promise.all(
    dirs.map((d) =>
      readFile(path.join(AGENTS_DIR, d, "agent.yaml"), "utf8").then(
        (text) => parse(text) as Agent,
        () => undefined, // a folder without agent.yaml is not an agent
      ),
    ),
  );
  return agents.filter((a): a is Agent => a !== undefined);
}

export async function getAgent(slug: string): Promise<Agent | undefined> {
  return (await listAgents()).find((a) => a.slug === slug);
}

// Platform admins can use every agent (platform.yaml, also read by scripts/gen-gateway.py)
const PLATFORM_FILE =
  process.env.PLATFORM_FILE ??
  path.resolve(process.cwd(), "../../platform.yaml");
let adminRoles: string[] | undefined;
async function getAdminRoles(): Promise<string[]> {
  adminRoles ??= (
    parse(await readFile(PLATFORM_FILE, "utf8")) as { admin_roles: string[] }
  ).admin_roles;
  return adminRoles;
}

/** UI gating only; the gateway enforces the same rule on every run. */
export async function canUse(agent: Agent, roles: string[]): Promise<boolean> {
  return [...agent.access.roles, ...(await getAdminRoles())].some((r) =>
    roles.includes(r),
  );
}

/** The agents this user may use, as browser-safe summaries, sorted by name. */
export async function listAllowed(roles: string[]): Promise<AgentSummary[]> {
  const all = await listAgents();
  const allowed = await Promise.all(all.map((a) => canUse(a, roles)));
  return all
    .filter((_, i) => allowed[i])
    .map(({ slug, name, description, owner_team, tags }) => ({
      slug,
      name,
      description,
      owner_team,
      tags: tags ?? [],
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
}
