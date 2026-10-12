"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Clock, Search, SearchX, Users, X } from "lucide-react";
import { getRecent, initials, matches, type AgentSummary } from "@/lib/agent-summary";

export function AgentCatalog({ agents, firstName }: { agents: AgentSummary[]; firstName?: string }) {
  const router = useRouter();
  const searchRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [tag, setTag] = useState<string | null>(null);
  const [recent, setRecent] = useState<string[]>([]);

  useEffect(() => setRecent(getRecent()), []);

  // "/" focuses the search, like most catalog and docs sites
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
      if (e.key === "/" && !typing) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const tags = useMemo(() => {
    const counts = new Map<string, number>();
    for (const a of agents) for (const t of a.tags) counts.set(t, (counts.get(t) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }, [agents]);

  const results = agents.filter((a) => matches(a, query) && (!tag || a.tags.includes(tag)));
  const recentAgents = recent.map((s) => agents.find((a) => a.slug === s)).filter((a): a is AgentSummary => !!a);
  const filtering = query !== "" || tag !== null;

  return (
    <div>
      <section className="bg-linear-to-b from-(--accent-surface) to-(--background)">
        <div className="mx-auto max-w-6xl px-4 pt-14 pb-10 sm:px-6 sm:pt-20">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            {firstName ? `Hi ${firstName}, how can we help?` : "How can we help?"}
          </h1>
          <p className="mt-2 text-(--muted-foreground)">Find an agent and start a conversation.</p>

          <form
            className="relative mt-8 max-w-2xl"
            onSubmit={(e) => {
              e.preventDefault();
              if (results[0]) router.push(`/chat/${results[0].slug}`);
            }}
          >
            <Search className="pointer-events-none absolute top-1/2 left-5 size-5 -translate-y-1/2 text-(--muted-foreground)" />
            <input
              ref={searchRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, topic or team"
              aria-label="Search agents"
              className="h-14 w-full rounded-(--radius-control) border border-(--border) bg-(--surface) pr-24 pl-13 text-[15px] shadow-[0_8px_30px_-16px_rgb(0_0_0/0.25)] outline-none placeholder:text-(--muted-foreground) focus:ring-2 focus:ring-(--focus-ring)"
            />
            {query ? (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => setQuery("")}
                className="absolute top-1/2 right-4 grid size-8 -translate-y-1/2 place-items-center rounded-full text-(--muted-foreground) hover:bg-(--muted)"
              >
                <X className="size-4" />
              </button>
            ) : (
              <kbd className="absolute top-1/2 right-5 hidden -translate-y-1/2 rounded-md border border-(--border) px-2 py-0.5 font-sans text-xs text-(--muted-foreground) sm:block">
                /
              </kbd>
            )}
          </form>

          {tags.length > 0 && (
            <div className="scrollbar-none -mx-4 mt-5 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0" role="group" aria-label="Filter by topic">
              <Chip active={tag === null} onClick={() => setTag(null)} label="All" count={agents.length} />
              {tags.map(([t, n]) => (
                <Chip key={t} active={tag === t} onClick={() => setTag(tag === t ? null : t)} label={t} count={n} />
              ))}
            </div>
          )}
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
        {!filtering && recentAgents.length > 0 && (
          <section className="mb-10">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-(--muted-foreground)">
              <Clock className="size-4" /> Recently used
            </h2>
            <div className="scrollbar-none -mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0">
              {recentAgents.slice(0, 4).map((a) => (
                <Link
                  key={a.slug}
                  href={`/chat/${a.slug}`}
                  className="flex shrink-0 items-center gap-2 rounded-(--radius-control) border border-(--border) bg-(--surface) py-1.5 pr-4 pl-1.5 text-sm whitespace-nowrap transition-colors hover:bg-(--muted)"
                >
                  <AgentIcon name={a.name} size="sm" />
                  {a.name}
                </Link>
              ))}
            </div>
          </section>
        )}

        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">{filtering ? "Results" : "All agents"}</h2>
          <span className="text-sm text-(--muted-foreground)" aria-live="polite">
            {results.length} {results.length === 1 ? "agent" : "agents"}
          </span>
        </div>

        {agents.length === 0 ? (
          <Empty title="No agents for you yet" body="Ask your team lead or a platform admin for access." />
        ) : results.length === 0 ? (
          <Empty
            title={`Nothing matches “${query || tag}”`}
            body="Try fewer or different words, or clear the filters."
            action={
              <button
                onClick={() => {
                  setQuery("");
                  setTag(null);
                }}
                className="rounded-(--radius-control) border border-(--border) px-4 py-1.5 text-sm hover:bg-(--muted)"
              >
                Clear filters
              </button>
            }
          />
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {results.map((a) => (
              <li key={a.slug}>
                <AgentCard agent={a} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Chip({ active, onClick, label, count }: { active: boolean; onClick: () => void; label: string; count: number }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`shrink-0 rounded-(--radius-control) border px-3.5 py-1 text-sm whitespace-nowrap transition-colors ${
        active
          ? "border-(--primary) bg-(--primary) text-(--primary-foreground)"
          : "border-(--border) bg-(--surface) hover:bg-(--muted)"
      }`}
    >
      {label} <span className={active ? "opacity-80" : "text-(--muted-foreground)"}>{count}</span>
    </button>
  );
}

export function AgentIcon({ name, size = "md" }: { name: string; size?: "sm" | "md" }) {
  const box = size === "sm" ? "size-7 rounded-full text-[10px]" : "size-11 rounded-2xl text-sm";
  return (
    <span className={`grid shrink-0 place-items-center bg-(--accent-surface) font-semibold text-(--accent) ${box}`}>
      {initials(name)}
    </span>
  );
}

function AgentCard({ agent }: { agent: AgentSummary }) {
  return (
    <Link
      href={`/chat/${agent.slug}`}
      className="group flex h-full flex-col rounded-(--radius-card) border border-(--border) bg-(--surface) p-5 transition-all hover:-translate-y-0.5 hover:border-(--accent) hover:shadow-[0_12px_32px_-16px_rgb(0_0_0/0.25)] focus-visible:ring-2 focus-visible:ring-(--focus-ring) focus-visible:outline-none"
    >
      <div className="flex items-start gap-3">
        <AgentIcon name={agent.name} />
        <div className="min-w-0">
          <div className="font-semibold leading-snug">{agent.name}</div>
          <div className="mt-0.5 flex items-center gap-1 text-xs text-(--muted-foreground)">
            <Users className="size-3" /> {agent.owner_team}
          </div>
        </div>
      </div>
      <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-(--muted-foreground)">{agent.description}</p>
      <div className="mt-auto flex items-end justify-between gap-3 pt-5">
        <div className="flex flex-wrap gap-1.5">
          {agent.tags.slice(0, 3).map((t) => (
            <span key={t} className="rounded-(--radius-control) bg-(--muted) px-2 py-0.5 text-xs">
              {t}
            </span>
          ))}
        </div>
        <span className="flex shrink-0 items-center gap-1 text-sm font-medium text-(--accent)">
          Start chat <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
        </span>
      </div>
    </Link>
  );
}

function Empty({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-(--radius-card) border border-dashed border-(--border) px-6 py-14 text-center">
      <SearchX className="size-8 text-(--muted-foreground)" />
      <p className="mt-3 font-medium">{title}</p>
      <p className="mt-1 text-sm text-(--muted-foreground)">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
