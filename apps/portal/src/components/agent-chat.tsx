"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { AssistantRuntimeProvider, type ThreadMessage } from "@assistant-ui/react";
import { HttpAgent } from "@ag-ui/client";
import { useAgUiRuntime } from "@assistant-ui/react-ag-ui";
import { NewChatButton, Thread } from "@/components/thread";

type Props = { slug: string; name: string; description: string; starterPrompts: string[]; placeholder: string };

/**
 * One plain AG-UI HttpAgent per agent, whatever its runtime: the portal route adds the user's token and
 * the gateway translates for runtimes that need it (Langflow).
 * Threads are in memory for now (P2 persists them).
 */
export function AgentChat({ slug, name, description, starterPrompts, placeholder }: Props) {
  const threads = useRef(new Map<string, readonly ThreadMessage[]>());
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());

  const agent = useMemo(
    () => new HttpAgent({ url: `/api/agents/${slug}/run`, threadId, headers: { Accept: "text/event-stream" } }),
    [slug, threadId],
  );

  const threadList = useMemo(
    () => ({
      threadId,
      onSwitchToNewThread: async () => setThreadId(crypto.randomUUID()),
      onSwitchToThread: async (id: string) => {
        setThreadId(id);
        return { messages: threads.current.get(id) ?? [] };
      },
    }),
    [threadId],
  );

  const runtime = useAgUiRuntime({
    agent,
    adapters: { threadList },
    onError: (e) => console.error("[agui]", e),
  });

  useEffect(
    () => runtime.thread.subscribe(() => threads.current.set(threadId, runtime.thread.getState().messages)),
    [runtime, threadId],
  );

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex h-full flex-col">
        <div className="mx-auto flex h-12 w-full max-w-6xl shrink-0 items-center justify-between px-4 sm:px-6">
          <Link
            href="/"
            className="-ml-2 flex items-center gap-1 rounded-full py-1 pr-3 pl-1.5 text-sm text-(--muted-foreground) transition-colors hover:bg-(--muted) hover:text-(--foreground) md:invisible"
          >
            <ChevronLeft className="size-4" />
            Agents
          </Link>
          <span className="truncate px-2 text-sm font-medium">{name}</span>
          <NewChatButton />
        </div>
        <div className="min-h-0 flex-1">
          <Thread agentName={name} description={description} starterPrompts={starterPrompts} placeholder={placeholder} />
        </div>
      </div>
    </AssistantRuntimeProvider>
  );
}
