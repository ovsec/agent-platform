// What the browser gets about an agent (no access rules or runtime details).
export type AgentSummary = {
  slug: string;
  name: string;
  description: string;
  owner_team: string;
  tags: string[];
};

/** All search words must appear in the agent's name, description, tags or team (case-insensitive). */
export function matches(agent: AgentSummary, query: string): boolean {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const haystack = [agent.name, agent.description, agent.owner_team, agent.slug, ...agent.tags].join(" ").toLowerCase();
  return words.every((w) => haystack.includes(w));
}

export function initials(name: string): string {
  return name
    .split(/[\s()]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}

const RECENT_KEY = "agent-portal:recent";

/** Recently opened agents, newest first. Per-browser convenience only; empty when storage is unavailable. */
export function getRecent(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

export function addRecent(slug: string): void {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify([slug, ...getRecent().filter((s) => s !== slug)].slice(0, 6)));
  } catch {
    // storage blocked (private mode, policy): recent list is optional
  }
}
