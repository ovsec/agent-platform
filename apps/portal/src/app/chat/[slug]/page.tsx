import { notFound, redirect } from "next/navigation";
import { currentSession } from "@/auth";
import { AgentChat } from "@/components/agent-chat";
import { AgentSidebar } from "@/components/agent-sidebar";
import { canUse, getAgent, listAllowed } from "@/lib/agents";
import { getBrand } from "@/lib/brand";

export default async function ChatPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const session = await currentSession();
  if (!session) redirect("/");

  const agent = await getAgent(slug);
  if (!agent || !(await canUse(agent, session.roles))) notFound();

  const agents = await listAllowed(session.roles);
  return (
    <div className="flex h-full">
      <AgentSidebar agents={agents} active={agent.slug} />
      <div className="min-w-0 flex-1">
        <AgentChat
          slug={agent.slug}
          name={agent.name}
          description={agent.description}
          starterPrompts={agent.starter_prompts ?? []}
          placeholder={getBrand().copy.composerPlaceholder}
        />
      </div>
    </div>
  );
}
