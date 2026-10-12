"""Generate docs/components.svg: python3 docs/make-components.py docs/components.svg

High-level components of the agent platform and what each one is for.
"""
import sys
from html import escape

import json

OUT = sys.argv[1]
SPEC_OUT = sys.argv[2] if len(sys.argv) > 2 else None  # generic layout for make-tldr.mjs
SPEC = {"boxes": [], "zones": [], "arrows": [], "texts": []}
W, H = 1600, 1010
# Theme: minimal tech (one rose accent, light/dark via light-dark(); works inline and as <img> on GitHub).
INK, MUTED, SURF = "var(--dg-ink)", "var(--dg-muted)", "var(--dg-surface)"
LINE, STRONG = "var(--dg-line)", "var(--dg-line-strong)"
ACCENT = "light-dark(#e11d48,#fb7185)"
SANS, MONO = "inherit", "var(--font-mono,ui-monospace,SFMono-Regular,Menlo,monospace)"
o = []
add = o.append


def t(x, y, s, size=13, fill=MUTED, weight=400, family=SANS, anchor="start", extra=""):
    add(f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" font-family="{family}"{extra}>{escape(s)}</text>')


def box(key, x, y, w, h, kind, title, purpose, tech):
    accent, plan = kind == "gw", kind == "plan"
    if accent:
        add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="color-mix(in srgb,{ACCENT} 10%,{SURF})" stroke="{ACCENT}" stroke-width="1.75"/>')
    else:
        dash = ' stroke-dasharray="5 4"' if plan else ""
        add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="none" stroke="{STRONG}" stroke-width="1"{dash}/>')
    if plan:
        t(x + w - 16, y + 26, "PLANNED", 10, MUTED, 500, MONO, "end", ' letter-spacing="0.08em"')
    t(x + 16, y + 28, title, 16, MUTED if plan else INK, 600)
    yy = y + 50
    for line in purpose:
        t(x + 16, yy, line, 13, MUTED)
        yy += 18
    if tech:
        t(x + 16, y + h - 14, tech, 11, MUTED, 400, MONO)
    BOX[key] = (x, y, w, h)
    SPEC["boxes"].append({"id": key, "x": x, "y": y, "w": w, "h": h, "kind": kind,
                          "lines": [title, *[l for l in purpose if l.strip()], *( [tech] if tech else [])]})


BOX = {}
VY, VH = 72, 836  # crop: no title band (the README heading names the diagram)
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {VY} {W} {VH}" role="img" '
    'aria-label="Agent platform components: end users, admins and developers reach agents through the portal and '
    'identity provider, every call passes the agentgateway front door to Langflow or planned code runtimes, which use '
    'LLMs and enterprise systems; developers build in Langflow Builder and publish from git without restarts." '
    'style="color-scheme:light dark;'
    '--dg-ink:var(--text-primary,light-dark(#18181b,#f4f4f8));--dg-muted:var(--text-secondary,light-dark(#52525b,#a1a1b5));'
    '--dg-surface:var(--surface-raised,light-dark(#ffffff,#121214));'
    '--dg-line:color-mix(in srgb,var(--dg-ink) 18%,var(--dg-surface));'
    '--dg-line-strong:color-mix(in srgb,var(--dg-ink) 50%,var(--dg-surface));'
    'width:100%;height:auto;display:block;font-family:var(--font-sans,system-ui,-apple-system,\'Segoe UI\',sans-serif)">')
add("<title>Agent platform: components and their purpose</title><defs>")
for mid_, color in [("m1l", STRONG), ("m1a", ACCENT)]:
    add(f'<marker id="{mid_}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">'
        f'<path d="M1 1 L8 5 L1 9" fill="none" stroke="{color}" stroke-width="1.5"/></marker>')
add("</defs>")


def zone(x, y, w, h, label):
    t(x, y + 10, label, 10.5, MUTED, 600, SANS, extra=' letter-spacing="0.12em"')
    add(f'<line x1="{x}" y1="{y + 18}" x2="{x + w}" y2="{y + 18}" stroke="{STRONG}"/>')
    SPEC["zones"].append({"x": x, "y": y, "w": w, "h": h, "label": label})


zone(24, 84, 276, 450, "PEOPLE")
zone(316, 84, 330, 450, "EXPERIENCE & IDENTITY")
zone(662, 84, 316, 450, "FRONT DOOR")
zone(994, 84, 290, 450, "AGENT RUNTIMES")
zone(1300, 84, 276, 450, "WHAT AGENTS USE")
zone(24, 554, 970, 236, "BUILD & PUBLISH")
zone(1010, 554, 566, 236, "STATE & INSIGHT")

box("users", 40, 110, 244, 128, "people", "End users", ["Find the right agent, ask", "questions, approve or reject", "actions the agent proposes."], "browser")
box("admins", 40, 254, 244, 128, "idp", "Agent admins", ["Govern models, tools and", "access; see who used what."], "role agent-admin")
box("devs", 40, 398, 244, 120, "dev", "Agent developers", ["Build and test agents, then", "publish them to the catalog."], "Langflow · code (planned)")

box("portal", 332, 110, 298, 214, "ui", "Portal", ["One place for every agent:", "sign in, search the catalog,", "chat with streaming answers,", "tool results and approval cards.", "Same experience whatever runtime", "is behind an agent."], "Next.js · assistant-ui · AG-UI · branding")
box("idp", 332, 340, 298, 178, "idp", "Identity provider (OIDC)", ["Who you are and which roles", "you have. One login for the", "portal and the gateway UI;", "any OIDC provider."], "Keycloak locally · Entra ID / Okta")

box("gw", 678, 110, 284, 408, "gw", "agentgateway", ["The single front door.", "", "• checks identity and roles", "  for every agent call", "• routes /agents/{slug}/run to", "  the right runtime", "• governs model and tool use:", "  keys, guardrails, budgets", "• records who called which agent", "  and which model (audit, analytics)", "• admin UI for models and MCP"], "agent API · admin UI · LLM/MCP services")

box("adapter", 1010, 110, 258, 128, "rt", "Langflow adapter", ["Lets Langflow agents speak", "standard AG-UI, incl. pausing", "for a human and resuming."], "FastAPI · stateless")
box("runtime", 1010, 254, 258, 128, "rt", "Langflow runtime", ["Runs the published visual", "agents, with per-user memory", "and human-in-the-loop."], "Langflow 1.12 · headless")
box("code", 1010, 398, 258, 120, "plan", "Code runtimes", ["Run code-first agents behind", "the same front door."], "Pydantic AI · LangGraph · CrewAI")

box("llm", 1316, 110, 244, 128, "ext", "LLM providers", ["The models agents think with,", "reached only through the", "gateway (keys stay there)."], "Ollama · cloud LLMs")
box("ent", 1316, 254, 244, 128, "ext", "Enterprise systems", ["The data and actions agents", "work on, through tools."], "Business system · APIs")
box("mcp", 1316, 398, 244, 120, "plan", "Shared tools (MCP)", ["Tools every runtime can use,", "governed by the gateway."], "MCP servers via gateway")

box("builder", 40, 580, 296, 194, "dev", "Langflow Builder", ["Where developers design and", "test agents visually: prompts,", "models, tools, human approval", "steps, in a playground."], "shared visual editor")
box("publish", 356, 580, 296, 194, "dev", "Publish (publish.py)", ["Turns a tested flow into a live", "catalog agent in one step, with", "no restarts: routes models via", "the gateway, updates runtime,", "catalog and gateway routes."], "later: run by CI on PR merge")
box("git", 672, 580, 306, 194, "data", "Git repository", ["Source of truth: flows, catalog", "entries (agents/*.yaml), gateway", "base config, components, portal,", "adapter. Reviewed by PR."], "flows/ · agents/ · gateway/ · apps/")

box("state", 1026, 580, 260, 194, "data", "Databases & volumes", ["Keep state: identities, flows,", "run jobs and memory, gateway", "UI settings and request logs,", "log-search index."], "Postgres · SQLite · DuckDB/Chroma")
box("obs", 1302, 580, 258, 194, "plan", "Observability", ["Searchable logs, metrics,", "traces and audit dashboards:", "usage, errors, latency, cost", "per agent and user."], "Alloy · Loki · Grafana (planned)")


def mid(k, side):
    if isinstance(side, tuple):  # explicit point
        return side
    x, y, w, h = BOX[k]
    return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y), "b": (x + w / 2, y + h)}[side]


def arrow(a, sa, b, sb, color="b", label=None, dashed=False, via=None):
    SPEC["arrows"].append({"from": a, "to": b, "color": color, "label": label, "dashed": dashed})
    (x1, y1), (x2, y2) = mid(a, sa), mid(b, sb)
    pts = [(x1, y1)] + (via or []) + [(x2, y2)]
    d = "M" + " L".join(f"{px:.0f},{py:.0f}" for px, py in pts)
    da = ' stroke-dasharray="5 4"' if dashed else ""
    add(f'<path d="{d}" stroke="{STRONG}" stroke-width="1.2" fill="none"{da} marker-end="url(#m1l)"/>')
    if label:
        lx, ly = (pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2
        t(lx, ly - 6, label, 10.5, MUTED, 400, MONO, "middle",
          extra=f' paint-order="stroke" stroke="{SURF}" stroke-width="4" stroke-linejoin="round"')


arrow("users", "r", "portal", (330, 174), "b")
arrow("portal", "r", "gw", (676, 217), "b", "AG-UI")
arrow("idp", "t", "portal", "b", "v")
arrow("idp", "r", "gw", (676, 429), "v", "tokens")
arrow("admins", "r", "gw", (820, 520), "v", None, via=[(310, 318), (310, 538), (820, 538)])
arrow("gw", (962, 174), "adapter", "l", "b", "/run")
arrow("gw", (962, 458), "code", "l", "s", None, dashed=True)
arrow("adapter", "b", "runtime", "t", "b")
arrow("runtime", (1268, 300), "llm", "l", "o", None, via=[(1292, 300), (1292, 174)])
arrow("runtime", (1268, 336), "ent", (1316, 336), "o")
arrow("code", "r", "mcp", "l", "s", None, dashed=True)
arrow("devs", "b", "builder", "t", "g")
arrow("builder", "r", "publish", "l", "g")
arrow("publish", "r", "git", "l", "g")
arrow("publish", "t", "runtime", "l", "g", "publish", via=[(504, 546), (988, 546), (988, 318)])

# legend
lx, ly = 40, 830
for label, dashed in [("call / flow", False), ("planned", True)]:
    da = ' stroke-dasharray="5 4"' if dashed else ""
    add(f'<line x1="{lx}" y1="{ly}" x2="{lx + 34}" y2="{ly}" stroke="{STRONG}" stroke-width="1.2"{da} marker-end="url(#m1l)"/>')
    t(lx + 44, ly + 4, label, 11, MUTED, 400, MONO)
    lx += 64 + len(label) * 7
add(f'<rect x="{lx}" y="{ly - 7}" width="22" height="14" rx="3" fill="color-mix(in srgb,{ACCENT} 10%,{SURF})" stroke="{ACCENT}" stroke-width="1.75"/>')
t(lx + 32, ly + 4, "the one door every agent, model and tool call passes", 11, MUTED, 400, MONO)
t(40, 870, "Principles: one front door (agentgateway) for agents, models and tools · standard AG-UI between portal and every runtime · generic OIDC ·", 13)
t(40, 888, "git as the source of truth and publish without restarts · provider keys and user tokens never reach the browser or the flows.", 13)
add("</svg>")
SPEC["texts"] = [{"x": 40, "y": 14, "text": "Agent platform · components and their purpose", "size": "l"},
                 {"x": 40, "y": 860, "text": "One front door (agentgateway) for agents, models and tools · standard AG-UI between portal and every runtime · generic OIDC · git as source of truth, publish without restarts · keys and user tokens never reach the browser or the flows. Dashed = planned.", "size": "s", "w": 1500}]
if SPEC_OUT:
    json.dump(SPEC, open(SPEC_OUT, "w"), indent=1)
open(OUT, "w").write("\n".join(o) + "\n")
print("wrote", OUT)
