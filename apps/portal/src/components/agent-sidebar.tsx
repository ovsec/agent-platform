"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LayoutGrid, Search } from "lucide-react";
import { AgentIcon } from "@/components/agent-catalog";
import { addRecent, matches, type AgentSummary } from "@/lib/agent-summary";

/** Desktop sidebar on the chat page: switch agents without going back to the catalog. */
export function AgentSidebar({ agents, active }: { agents: AgentSummary[]; active: string }) {
  const [query, setQuery] = useState("");
  useEffect(() => addRecent(active), [active]);
  const shown = agents.filter((a) => matches(a, query));

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-(--border) bg-(--surface) md:flex lg:w-72">
      <div className="p-3">
        <Link
          href="/"
          className="mb-3 flex items-center gap-2 rounded-(--radius-control) px-3 py-2 text-sm text-(--muted-foreground) hover:bg-(--muted) hover:text-(--foreground)"
        >
          <LayoutGrid className="size-4" /> All agents
        </Link>
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-(--muted-foreground)" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find an agent"
            aria-label="Find an agent"
            className="h-9 w-full rounded-(--radius-control) border border-(--border) bg-(--background) pr-3 pl-9 text-sm outline-none focus:ring-2 focus:ring-(--focus-ring)"
          />
        </div>
      </div>
      <nav className="min-h-0 flex-1 overflow-y-auto px-3 pb-4" aria-label="Agents">
        {shown.map((a) => {
          const current = a.slug === active;
          return (
            <Link
              key={a.slug}
              href={`/chat/${a.slug}`}
              aria-current={current ? "page" : undefined}
              className={`mb-0.5 flex items-center gap-2.5 rounded-(--radius-control) px-2 py-2 text-sm transition-colors ${
                current ? "bg-(--accent-surface) font-medium text-(--accent)" : "hover:bg-(--muted)"
              }`}
            >
              <AgentIcon name={a.name} size="sm" />
              <span className="truncate">{a.name}</span>
            </Link>
          );
        })}
        {shown.length === 0 && <p className="px-2 py-4 text-sm text-(--muted-foreground)">No agent matches.</p>}
      </nav>
    </aside>
  );
}
