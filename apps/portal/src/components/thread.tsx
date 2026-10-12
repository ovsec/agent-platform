"use client";

import {
  ActionBarPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAui,
  useAuiState,
  type ToolCallMessagePartProps,
} from "@assistant-ui/react";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";
import { PendingInterrupts } from "@/components/interrupts";
import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronRight,
  Copy,
  LoaderCircle,
  RefreshCw,
  SquarePen,
  Square,
  Wrench,
} from "lucide-react";

type ThreadProps = {
  agentName: string;
  description: string;
  starterPrompts: string[];
  placeholder: string;
};

export function Thread({
  agentName,
  description,
  starterPrompts,
  placeholder,
}: ThreadProps) {
  return (
    <ThreadPrimitive.Root className="flex h-full flex-col">
      <ThreadPrimitive.Viewport className="relative flex flex-1 flex-col items-center overflow-y-auto px-4">
        <ThreadPrimitive.Empty>
          <div className="flex w-full max-w-2xl flex-1 flex-col justify-center pb-8">
            <h2 className="text-3xl font-semibold tracking-tight">
              {agentName}
            </h2>
            <p className="mt-2 text-(--muted-foreground)">{description}</p>
            {starterPrompts.length > 0 && (
              <div className="mt-8 flex flex-col gap-2">
                {starterPrompts.map((prompt) => (
                  <ThreadPrimitive.Suggestion
                    key={prompt}
                    prompt={prompt}
                    send
                    className="group flex items-center justify-between rounded-(--radius-card) border border-(--border) bg-(--surface) px-4 py-3 text-left text-sm transition-colors hover:bg-(--muted)"
                  >
                    {prompt}
                    <ArrowUp className="size-4 rotate-45 text-(--muted-foreground) opacity-0 transition-opacity group-hover:opacity-100" />
                  </ThreadPrimitive.Suggestion>
                ))}
              </div>
            )}
          </div>
        </ThreadPrimitive.Empty>

        <div className="w-full max-w-2xl pt-8">
          <ThreadPrimitive.Messages>
            {({ message }) =>
              message.role === "user" ? <UserMessage /> : <AssistantMessage />
            }
          </ThreadPrimitive.Messages>
          <WaitingForAgent />
          <PendingInterrupts />
        </div>

        <ThreadPrimitive.If empty={false}>
          <div className="min-h-10 flex-grow" />
        </ThreadPrimitive.If>

        <div className="sticky bottom-0 w-full max-w-2xl bg-linear-to-t from-(--background) from-60% to-transparent pt-6 pb-5">
          <ThreadPrimitive.ScrollToBottom className="absolute -top-6 left-1/2 grid size-8 -translate-x-1/2 place-items-center rounded-full border border-(--border) bg-(--surface) text-(--muted-foreground) shadow-sm disabled:invisible">
            <ArrowDown className="size-4" />
          </ThreadPrimitive.ScrollToBottom>
          <Composer placeholder={placeholder} />
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

const iconButton =
  "grid size-8 shrink-0 place-items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-30";

function Composer({ placeholder }: { placeholder: string }) {
  return (
    <ComposerPrimitive.Root className="flex items-end gap-2 rounded-[calc(var(--radius-card)+0.25rem)] border border-(--border) bg-(--surface) py-2 pr-2 pl-4 shadow-[0_8px_30px_-12px_rgb(0_0_0/0.15)] transition-shadow focus-within:ring-2 focus-within:ring-(--focus-ring)">
      <ComposerPrimitive.Input
        autoFocus
        rows={1}
        placeholder={placeholder}
        className="max-h-48 flex-1 resize-none bg-transparent py-1.5 text-[15px] outline-none placeholder:text-(--muted-foreground)"
      />
      <ThreadPrimitive.If running={false}>
        <ComposerPrimitive.Send
          aria-label="Send"
          className={`${iconButton} bg-(--primary) text-(--primary-foreground) hover:bg-(--primary-hover)`}
        >
          <ArrowUp className="size-4" />
        </ComposerPrimitive.Send>
      </ThreadPrimitive.If>
      <ThreadPrimitive.If running>
        <ComposerPrimitive.Cancel
          aria-label="Stop"
          className={`${iconButton} bg-(--foreground) text-(--background)`}
        >
          <Square className="size-3 fill-current" />
        </ComposerPrimitive.Cancel>
      </ThreadPrimitive.If>
    </ComposerPrimitive.Root>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex w-full justify-end py-3">
      <div className="max-w-[85%] rounded-(--radius-bubble) bg-(--user-bubble) px-4 py-2.5 text-[15px] whitespace-pre-wrap text-(--user-bubble-foreground)">
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  // a run that paused for a human can leave an empty text part: no copy/regenerate on that
  const visible = useAuiState((st) =>
    st.message.parts.some(
      (p) => p.type !== "text" || ("text" in p && String(p.text).trim() !== ""),
    ),
  );
  // the agent is working but has nothing new to show: before the first token, and while the model
  // reads a tool result and decides what to do next
  const thinking = useAuiState((st) => {
    if (st.message.status?.type !== "running") return false;
    const last = st.message.parts.at(-1);
    if (!last || last.type === "reasoning") return true;
    if (last.type === "text") return String(last.text).trim() === "";
    if (last.type === "tool-call") return last.result !== undefined;
    return false;
  });
  return (
    <MessagePrimitive.Root className="group w-full py-3">
      <div className="text-[15px] leading-7">
        <MessagePrimitive.Parts
          components={{ Text: MarkdownText, tools: { Fallback: ToolCall } }}
        />
        {thinking && <Thinking />}
        <MessagePrimitive.Error>
          <p className="mt-2 rounded-(--radius-control) bg-(--danger-surface) px-3 py-2 text-sm text-(--danger)">
            The agent run failed. Check that you have access to this agent and
            try again.
          </p>
        </MessagePrimitive.Error>
      </div>
      {visible && (
        <ActionBarPrimitive.Root
          hideWhenRunning
          autohide="not-last"
          className="mt-1 -ml-1.5 flex gap-0.5 text-(--muted-foreground) data-floating:opacity-0 data-floating:transition-opacity group-hover:data-floating:opacity-100"
        >
          <ActionBarPrimitive.Copy
            aria-label="Copy"
            className={`${iconButton} size-7 hover:bg-(--muted)`}
          >
            <MessagePrimitive.If copied>
              <Check className="size-3.5" />
            </MessagePrimitive.If>
            <MessagePrimitive.If copied={false}>
              <Copy className="size-3.5" />
            </MessagePrimitive.If>
          </ActionBarPrimitive.Copy>
          <ActionBarPrimitive.Reload
            aria-label="Regenerate"
            className={`${iconButton} size-7 hover:bg-(--muted)`}
          >
            <RefreshCw className="size-3.5" />
          </ActionBarPrimitive.Reload>
        </ActionBarPrimitive.Root>
      )}
    </MessagePrimitive.Root>
  );
}

/** Run started but the agent's reply has not appeared yet (no assistant message in the thread so far). */
function WaitingForAgent() {
  const waiting = useAuiState(
    (st) => st.thread.isRunning && st.thread.messages.at(-1)?.role === "user",
  );
  return waiting ? (
    <div className="py-3">
      <Thinking />
    </div>
  ) : null;
}

function Thinking() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 py-1 text-sm text-(--muted-foreground)"
    >
      <span className="flex gap-1" aria-hidden>
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-1.5 animate-bounce rounded-full bg-current"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
      Thinking…
    </div>
  );
}

const MarkdownText = () => (
  <MarkdownTextPrimitive remarkPlugins={[remarkGfm]} className="aui-md" />
);

/** Generic renderer for any tool call the agent streams (AG-UI TOOL_CALL_* events): a quiet, expandable line. */
function ToolCall({
  toolName,
  argsText,
  result,
  status,
}: ToolCallMessagePartProps) {
  const running = status.type === "running";
  return (
    <details className="group/tool my-2 text-sm">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 rounded-(--radius-control) py-1 pr-2 text-(--muted-foreground) transition-colors select-none hover:text-(--foreground) [&::-webkit-details-marker]:hidden">
        {running ? (
          <LoaderCircle className="size-3.5 animate-spin" />
        ) : (
          <Wrench className="size-3.5" />
        )}
        <span>
          {running ? "Running" : "Used"}{" "}
          <span className="font-medium text-(--foreground)">{toolName}</span>
        </span>
        <ChevronRight className="size-3.5 transition-transform group-open/tool:rotate-90" />
      </summary>
      <div className="mt-1 space-y-2 rounded-(--radius-card) bg-(--muted) p-3 font-mono text-xs leading-5">
        {argsText && (
          <pre className="overflow-x-auto whitespace-pre-wrap">{argsText}</pre>
        )}
        {result !== undefined && (
          <pre className="max-h-64 overflow-auto border-t border-(--border) pt-2 whitespace-pre-wrap text-(--muted-foreground)">
            {typeof result === "string"
              ? result
              : JSON.stringify(result, null, 2)}
          </pre>
        )}
      </div>
    </details>
  );
}

export function NewChatButton() {
  const aui = useAui();
  return (
    <button
      type="button"
      title="New chat"
      aria-label="New chat"
      onClick={() => aui.threads().switchToNewThread()}
      className={`${iconButton} text-(--muted-foreground) hover:bg-(--muted) hover:text-(--foreground)`}
    >
      <SquarePen className="size-4" />
    </button>
  );
}
