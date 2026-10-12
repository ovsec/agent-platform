"use client";

import { useState } from "react";
import {
  useAgUiInterrupts,
  useAgUiSubmitInterruptResponses,
  type AgUiInterrupt,
} from "@assistant-ui/react-ag-ui";
import { Hand, ShieldQuestion, X } from "lucide-react";

/**
 * Generic human-in-the-loop card for standard AG-UI interrupts (RUN_FINISHED outcome "interrupt"), whatever
 * runtime raised them. A `responseSchema` with one enum property renders as decision buttons; any other
 * object schema renders as a small form. The answer resumes the run (RunAgentInput.resume).
 */
export function PendingInterrupts() {
  const interrupts = useAgUiInterrupts();
  if (interrupts.length === 0) return null;
  return (
    <div className="flex w-full flex-col gap-3 py-3">
      {interrupts.map((interrupt) => (
        <InterruptCard key={interrupt.id} interrupt={interrupt} />
      ))}
    </div>
  );
}

type JsonSchema = {
  type?: string;
  title?: string;
  description?: string;
  enum?: string[];
  "x-labels"?: Record<string, string>;
  properties?: Record<string, JsonSchema>;
  required?: string[];
};

function InterruptCard({ interrupt }: { interrupt: AgUiInterrupt }) {
  const submit = useAgUiSubmitInterruptResponses();
  const [busy, setBusy] = useState(false);
  const schema = (interrupt.responseSchema ?? {}) as JsonSchema;
  const props = Object.entries(schema.properties ?? {});
  const choice = props.length === 1 && props[0][1].enum ? props[0] : null;
  const meta = (interrupt.metadata ?? {}) as {
    tool?: string;
    toolArgs?: unknown;
  };

  const respond = async (
    status: "resolved" | "cancelled",
    payload?: unknown,
  ) => {
    setBusy(true);
    try {
      await submit([{ interruptId: interrupt.id, status, payload }]);
    } finally {
      setBusy(false);
    }
  };

  const isTool = interrupt.reason === "tool_call";
  return (
    <div className="rounded-(--radius-card) border border-(--border) bg-(--surface) p-4 shadow-[0_8px_30px_-16px_rgb(0_0_0/0.2)]">
      <div className="flex items-start gap-3">
        <div className="grid size-8 shrink-0 place-items-center rounded-full bg-(--accent-surface) text-(--accent)">
          {isTool ? (
            <ShieldQuestion className="size-4" />
          ) : (
            <Hand className="size-4" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium tracking-wide text-(--muted-foreground) uppercase">
            {isTool ? "Approval needed" : "Your input is needed"}
          </div>
          <p className="mt-1 text-[15px] whitespace-pre-wrap">
            {/* for a tool call the details box below shows tool and arguments; keep the message's first line */}
            {(isTool && meta.tool
              ? interrupt.message?.split("\n")[0]
              : interrupt.message) ?? "The agent is waiting for you."}
          </p>
          {isTool && meta.tool && (
            <pre className="mt-2 overflow-x-auto rounded-(--radius-control) bg-(--muted) px-3 py-2 font-mono text-xs">
              {meta.tool}
              {meta.toolArgs !== undefined
                ? ` ${JSON.stringify(meta.toolArgs, null, 2)}`
                : ""}
            </pre>
          )}

          {choice ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {choice[1].enum!.map((value, i) => (
                <button
                  key={value}
                  disabled={busy}
                  onClick={() => respond("resolved", { [choice[0]]: value })}
                  className={
                    i === 0
                      ? "rounded-(--radius-control) bg-(--primary) px-4 py-1.5 text-sm font-medium text-(--primary-foreground) hover:bg-(--primary-hover) disabled:opacity-50"
                      : "rounded-(--radius-control) border border-(--border) px-4 py-1.5 text-sm hover:bg-(--muted) disabled:opacity-50"
                  }
                >
                  {choice[1]["x-labels"]?.[value] ?? value}
                </button>
              ))}
            </div>
          ) : (
            <SchemaForm
              schema={schema}
              busy={busy}
              onSubmit={(payload) => respond("resolved", payload)}
            />
          )}
        </div>
        <button
          title="Dismiss and cancel"
          aria-label="Cancel"
          disabled={busy}
          onClick={() => respond("cancelled")}
          className="grid size-7 shrink-0 place-items-center rounded-full text-(--muted-foreground) hover:bg-(--muted)"
        >
          <X className="size-4" />
        </button>
      </div>
      {interrupt.expiresAt && (
        <div className="mt-3 text-xs text-(--muted-foreground)">
          Waits until {new Date(interrupt.expiresAt).toLocaleString()}
        </div>
      )}
    </div>
  );
}

/** Minimal form for object schemas: strings, numbers, booleans, enums; anything else as JSON. */
function SchemaForm({
  schema,
  busy,
  onSubmit,
}: {
  schema: JsonSchema;
  busy: boolean;
  onSubmit: (v: unknown) => void;
}) {
  const fields = Object.entries(schema.properties ?? {});
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [raw, setRaw] = useState("");
  const set = (k: string, v: unknown) =>
    setValues((prev) => ({ ...prev, [k]: v }));
  const input =
    "w-full rounded-(--radius-control) border border-(--border) bg-transparent px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-(--focus-ring)";

  return (
    <form
      className="mt-4 flex flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (fields.length) onSubmit(values);
        else {
          try {
            onSubmit(raw ? JSON.parse(raw) : raw);
          } catch {
            onSubmit(raw);
          }
        }
      }}
    >
      {fields.length === 0 && (
        <textarea
          rows={3}
          className={input}
          placeholder="Your answer"
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
        />
      )}
      {fields.map(([name, f]) => (
        <label key={name} className="flex flex-col gap-1 text-sm">
          <span className="text-(--muted-foreground)">
            {f.title ?? name}
            {schema.required?.includes(name) ? " *" : ""}
          </span>
          {f.enum ? (
            <select
              className={input}
              value={String(values[name] ?? "")}
              onChange={(e) => set(name, e.target.value)}
            >
              <option value="" disabled>
                Choose…
              </option>
              {f.enum.map((v) => (
                <option key={v} value={v}>
                  {f["x-labels"]?.[v] ?? v}
                </option>
              ))}
            </select>
          ) : f.type === "boolean" ? (
            <input
              type="checkbox"
              className="size-4"
              checked={Boolean(values[name])}
              onChange={(e) => set(name, e.target.checked)}
            />
          ) : (
            <input
              className={input}
              type={
                f.type === "number" || f.type === "integer" ? "number" : "text"
              }
              required={schema.required?.includes(name)}
              onChange={(e) =>
                set(
                  name,
                  f.type === "number" || f.type === "integer"
                    ? Number(e.target.value)
                    : e.target.value,
                )
              }
            />
          )}
        </label>
      ))}
      <div>
        <button
          disabled={busy}
          className="rounded-(--radius-control) bg-(--primary) px-4 py-1.5 text-sm font-medium text-(--primary-foreground) hover:bg-(--primary-hover) disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </form>
  );
}
