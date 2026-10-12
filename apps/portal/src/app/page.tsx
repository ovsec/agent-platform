import { Bot } from "lucide-react";
import { AgentCatalog } from "@/components/agent-catalog";
import { currentSession, signIn } from "@/auth";
import { listAllowed } from "@/lib/agents";
import { getBrand } from "@/lib/brand";

export default async function Home() {
  const brand = getBrand();
  const session = await currentSession();

  if (!session) {
    return (
      <div className="grid h-full place-items-center px-4">
        <div className="w-full max-w-sm text-center">
          <div className="mx-auto mb-6 grid size-12 place-items-center rounded-2xl bg-(--accent-surface) text-(--accent)">
            <Bot className="size-6" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {brand.copy.signedOutTitle}
          </h1>
          <p className="mt-2 text-sm text-(--muted-foreground)">
            {brand.copy.signedOutBody}
          </p>
          <form
            className="mt-8"
            action={async () => {
              "use server";
              await signIn("oidc");
            }}
          >
            <button className="w-full rounded-(--radius-control) bg-(--primary) px-4 py-2.5 text-sm font-medium text-(--primary-foreground) transition-colors hover:bg-(--primary-hover)">
              Sign in
            </button>
          </form>
          {brand.copy.footer && (
            <p className="mt-10 text-xs text-(--muted-foreground)">
              {brand.copy.footer}
            </p>
          )}
        </div>
      </div>
    );
  }

  const agents = await listAllowed(session.roles);
  return (
    <AgentCatalog
      agents={agents}
      firstName={session.user?.name?.split(" ")[0]}
    />
  );
}
