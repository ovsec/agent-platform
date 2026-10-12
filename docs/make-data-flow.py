"""Generate docs/data-flow.svg: python3 docs/make-data-flow.py docs/data-flow.svg"""
import sys
from html import escape

import json

OUT = sys.argv[1]
SPEC_OUT = sys.argv[2] if len(sys.argv) > 2 else None  # generic layout for make-tldr.mjs
SPEC = {"boxes": [], "zones": [], "arrows": [], "texts": [], "lines": []}
KIND_COLOR = {"req": "b", "ret": "b", "id": "v", "llm": "o", "hitl": "r", "pub": "g", "adm": "v"}
W = 1600

LANES = [  # key, title, subtitle, color
    ("br", "Browser", "end user", "#334155"),
    ("po", "Portal", "Next.js :3100", "#005d92"),
    ("idp", "OIDC IdP", "Keycloak / Entra", "#7c3aed"),
    ("gw", "agentgateway", ":4100 agent API", "#2563eb"),
    ("ad", "Langflow adapter", "AG-UI ↔ Workflow API", "#0d9488"),
    ("rt", "Langflow runtime", "flows, memory, HITL", "#0d9488"),
    ("sv", "agentgateway", ":4102 LLM / MCP", "#2563eb"),
    ("ex", "Ollama · business APIs", "models · tools", "#d97706"),
]
X = {k: 95 + i * 200 for i, (k, *_r) in enumerate(LANES)}
COL = {"req": "#2563eb", "ret": "#2563eb", "id": "#7c3aed", "llm": "#d97706", "hitl": "#db2777", "pub": "#059669", "adm": "#7c3aed"}

out = []
add = out.append


def text(x, y, s, cls="t", anchor="start", fill=None):
    f = f' fill="{fill}"' if fill else ""
    add(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"{f}>{escape(s)}</text>')


def msg(n, a, b, y, label, kind="req", sub=None, dashed=False):
    x1, x2 = X[a], X[b]
    SPEC["arrows"].append({"x1": x1, "y1": y, "x2": x2, "y2": y, "color": KIND_COLOR[kind], "dashed": dashed})
    # labels as free text (tldraw would wrap an arrow label to the arrow's length)
    SPEC["texts"].append({"x": min(x1, x2) + 12, "y": y - 22, "text": f"{n}. {label}"})
    if sub:
        SPEC["texts"].append({"x": min(x1, x2) + 12, "y": y + 3, "text": sub, "color": "grey"})
    d = 1 if x2 > x1 else -1
    color = COL[kind]
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    add(f'<path d="M{x1 + d * 6},{y} L{x2 - d * 8},{y}" stroke="{color}" stroke-width="1.8" fill="none"{dash} marker-end="url(#m-{kind})"/>')
    lx = (x1 + x2) / 2
    add(f'<circle cx="{min(x1, x2) + 16}" cy="{y - 13}" r="9" fill="{color}"/>')
    text(min(x1, x2) + 16, y - 9, str(n), "num", "middle")
    text(min(x1, x2) + 30, y - 9, label, "ml")
    if sub:
        text(min(x1, x2) + 30, y + 14, sub, "ms")


def note(lane, y, lines, kind="req", w=176):
    x = X[lane] - w / 2
    h = 14 + 15 * len(lines)
    tw = max(w, 250)  # tldraw text is wider: widen rather than grow, so the next arrow stays clear
    SPEC["boxes"].append({"id": f"note{len(SPEC['boxes'])}", "x": X[lane] - tw / 2, "y": y, "w": tw, "h": h,
                          "kind": "note-" + kind, "lines": lines})
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#ffffff" stroke="{COL[kind]}" stroke-width="1.2"/>')
    for i, line in enumerate(lines):
        text(x + 8, y + 18 + 15 * i, line, "nt")
    return y + h


def section(y, h, title, subtitle):
    SPEC["zones"].append({"x": 20, "y": y, "w": W - 40, "h": h, "label": f"{title} · {subtitle}"})
    add(f'<rect x="20" y="{y}" width="{W - 40}" height="{h}" rx="10" fill="none" stroke="#cbd5e1" stroke-dasharray="4 4"/>')
    text(32, y + 18, title, "sec")
    text(32, y + 34, subtitle, "s")


# header + lanes
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 1500" width="{W}" height="1500" font-family="-apple-system, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif">')
add("<title>Agent platform: data flow</title><defs>")
for k, c in COL.items():
    add(f'<marker id="m-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
add("""<style>
.t{font-size:12px;fill:#334155}.s{font-size:11px;fill:#64748b}.sec{font-size:12px;font-weight:700;fill:#475569;letter-spacing:1px}
.ml{font-size:12px;fill:#0f172a;paint-order:stroke;stroke:#f8fafc;stroke-width:4px}
.ms{font-size:11px;fill:#64748b;paint-order:stroke;stroke:#f8fafc;stroke-width:4px}
.nt{font-size:11px;fill:#334155}.num{font-size:10px;font-weight:700;fill:#ffffff}
.lh{font-size:13px;font-weight:700;fill:#0f172a}.lsub{font-size:11px;fill:#64748b}
</style></defs>""")
add(f'<rect width="{W}" height="1500" fill="#f8fafc"/>')
text(40, 42, "Agent platform · data flow", "t")
out[-1] = out[-1].replace('class="t"', 'font-size="24" font-weight="800" fill="#0f172a"')
text(40, 64, "What travels where for sign-in, an agent run, human-in-the-loop, and publishing. Numbers give the order; dashed = responses / streams.", "s")

LANE_TOP, LANE_BOTTOM = 84, 1270
for k, title, sub, c in LANES:
    x = X[k]
    add(f'<rect x="{x - 88}" y="{LANE_TOP}" width="176" height="52" rx="8" fill="#ffffff" stroke="{c}" stroke-width="1.6"/>')
    SPEC["boxes"].append({"id": f"lane-{k}", "x": x - 88, "y": LANE_TOP, "w": 176, "h": 52, "kind": "lane", "lines": [title, sub], "center": True})
    SPEC["lines"].append({"x": x, "y1": LANE_TOP + 52, "lane": k})
    text(x, LANE_TOP + 22, title, "lh", "middle")
    text(x, LANE_TOP + 40, sub, "lsub", "middle")
    add(f'<line x1="{x}" y1="{LANE_TOP + 52}" x2="{x}" y2="LIFELINE_END" stroke="#cbd5e1" stroke-width="1.2" stroke-dasharray="3 5"/>')

# sections are outlined after their content, so their height follows the steps
def outline(top, bottom, title, subtitle):
    section(top, bottom - top, title, subtitle)

# A. sign-in
top = 150
msg(1, "br", "po", top + 62, "Sign in", "id")
msg(2, "br", "idp", top + 102, "redirect → login page (username / password, MFA in Entra)", "id", "authorization_endpoint on the public issuer (localhost:8180)")
msg(3, "idp", "po", top + 150, "code → token exchange (server side)", "id", "via OIDC_INTERNAL_ISSUER (keycloak:8080); access + refresh token in encrypted cookie", dashed=True)
outline(top, top + 180, "A · SIGN-IN", "generic OAuth2 / OIDC code flow with PKCE")

# B. agent run
top = 346
msg(4, "br", "po", top + 64, "POST /api/agents/{slug}/run", "req", "RunAgentInput {threadId, runId, messages}")
msg(5, "po", "gw", top + 112, "+ Authorization: Bearer <access token>", "req", "+ x-agui-thread-id")
y = note("gw", top + 136, ["validate JWT (iss, aud, exp; JWKS", "from IdP) · CEL: roles ∩ agent roles", "audit log: user, agent, thread"], "req", 186)
msg(6, "gw", "ad", y + 32, "POST /run (no user token)", "req", "x-langflow-flow-id · x-end-user-id · x-api-key")
y = note("ad", y + 56, ["flow can pause? (cached 30 s)", "no → mode stream (tokens)", "yes → mode background + events"], "req")
msg(7, "ad", "rt", y + 32, "POST /api/v2/workflows", "req", "flow_id · input_value · session_id = threadId")
y = note("rt", y + 56, ["session = <user>::<thread>", "Agent: plan, call model/tools"], "req")
msg(8, "rt", "sv", y + 32, "POST /v1/chat/completions", "llm", "runtime key · x-end-user-id · x-agent-slug · x-agui-thread-id")
msg(9, "sv", "ex", y + 76, "ollama/qwen3:8b → Ollama", "llm", "Logs/Analytics: user, agent, tokens")
msg(10, "rt", "ex", y + 120, "tool call (make_api_request → business API)", "llm")
msg(11, "rt", "ad", y + 170, "AG-UI SSE events", "ret", "TEXT_MESSAGE_* · TOOL_CALL_* · RUN_FINISHED", dashed=True)
msg(12, "ad", "br", y + 220, "same events with the client's threadId/runId, langflow.* dropped → back through gateway and portal", "ret", "portal renders tokens, tool cards, markdown", dashed=True)
bottom = y + 250
outline(top, bottom, "B · AGENT RUN", "standard AG-UI end to end; Langflow translated by the adapter")

# C. HITL
top = bottom + 16
y = note("rt", top + 44, ["Human Input node, or a tool", "with approval_actions → pause"], "hitl")
msg(13, "rt", "ad", y + 34, "CUSTOM langflow.human_input_required", "hitl", "request_id · options · prompt", dashed=True)
msg(14, "ad", "br", y + 82, "RUN_FINISHED {outcome: interrupt}", "hitl", "id = job + request + event id · message · responseSchema (options) · expiresAt", dashed=True)
msg(15, "br", "ad", y + 136, "new run with resume: [{interruptId, status, payload: {action_id}}]", "hitl", "via portal (Bearer) and gateway (JWT, roles) as in 4–6")
msg(16, "ad", "rt", y + 186, "POST /{job}/resume + GET /{job}/events (Last-Event-ID)", "hitl", "cancelled → POST /stop · other user → 'job not found'")
msg(17, "rt", "br", y + 236, "remaining events (branch output / tool result, answer) → portal", "ret", "as in 11–12", dashed=True)
bottom = y + 266
outline(top, bottom, "C · HUMAN IN THE LOOP", "Langflow pause/resume mapped to standard AG-UI interrupts (stateless adapter)")
D_TOP = bottom + 16

# D. control plane
section(D_TOP, 270, "D · CONTROL PLANE", "no restarts: Langflow API upserts, gateway hot-reloads config.yaml, UI overlay in the gateway DB")
boxes = [
    (40, "Developer", "builds a flow in the Langflow Builder (:7870)"),
    (330, "publish.py", "export · gateway model · flows/ + agents/"),
    (620, "Langflow runtime", "upsert flow by API (+ Builder)"),
    (910, "gen-gateway.py", "config.yaml ← base + agents/ + platform.yaml"),
    (1200, "agentgateway", "watches config.yaml → route live in seconds"),
]
for x, h, sub in boxes:
    SPEC["boxes"].append({"id": f"pub-{x}", "x": x, "y": D_TOP + 64, "w": 250, "h": 56, "kind": "dev", "lines": [h, sub]})
    add(f'<rect x="{x}" y="{D_TOP + 64}" width="250" height="56" rx="8" fill="#ecfdf5" stroke="#059669" stroke-width="1.4"/>')
    text(x + 12, D_TOP + 86, h, "lh")
    text(x + 12, D_TOP + 106, sub, "nt")
for i in range(len(boxes) - 1):
    SPEC["arrows"].append({"from": f"pub-{boxes[i][0]}", "to": f"pub-{boxes[i + 1][0]}", "color": "g"})
    x = boxes[i][0] + 250
    add(f'<path d="M{x + 4},{D_TOP + 92} L{boxes[i + 1][0] - 6},{D_TOP + 92}" stroke="#059669" stroke-width="1.8" marker-end="url(#m-pub)"/>')
boxes2 = [
    (40, "Agent admin", "signs in to the gateway UI (:4101, OIDC, agent-admin)"),
    (420, "Gateway UI", "adds LLM providers / models, MCP servers, policies"),
    (800, "agw_data overlay", "stored in the gateway DB, survives regeneration"),
    (1180, ":4102 services", "serves the new model / tools to all runtimes"),
]
for x, h, sub in boxes2:
    SPEC["boxes"].append({"id": f"adm-{x}", "x": x, "y": D_TOP + 154, "w": 330, "h": 56, "kind": "idp", "lines": [h, sub]})
    add(f'<rect x="{x}" y="{D_TOP + 154}" width="330" height="56" rx="8" fill="#f5f3ff" stroke="#7c3aed" stroke-width="1.4"/>')
    text(x + 12, D_TOP + 176, h, "lh")
    text(x + 12, D_TOP + 196, sub, "nt")
for i in range(len(boxes2) - 1):
    SPEC["arrows"].append({"from": f"adm-{boxes2[i][0]}", "to": f"adm-{boxes2[i + 1][0]}", "color": "v"})
    x = boxes2[i][0] + 330
    add(f'<path d="M{x + 4},{D_TOP + 182} L{boxes2[i + 1][0] - 6},{D_TOP + 182}" stroke="#7c3aed" stroke-width="1.8" marker-end="url(#m-adm)"/>')
text(40, D_TOP + 244, "Secrets never in the browser: access/refresh tokens stay in the portal's encrypted cookie; the Langflow key is added by the gateway; provider keys live only in the gateway.", "s")

# legend
LEG = D_TOP + 300
lx = 40
for kind, label in [("req", "request"), ("ret", "response / stream (dashed)"), ("id", "identity"), ("llm", "model / tool call"),
                    ("hitl", "human in the loop"), ("pub", "publish"), ("adm", "admin config")]:
    dash = ' stroke-dasharray="6 4"' if kind == "ret" else ""
    add(f'<line x1="{lx}" y1="{LEG}" x2="{lx + 34}" y2="{LEG}" stroke="{COL[kind]}" stroke-width="2"{dash} marker-end="url(#m-{kind})"/>')
    text(lx + 42, LEG + 4, label, "s")
    lx += 52 + len(label) * 6.2 + 30
out[:] = [o.replace("LIFELINE_END", str(D_TOP - 6)) for o in out]
H = LEG + 30
for ln in SPEC["lines"]:
    ln["y2"] = D_TOP - 6
SPEC["scale"] = 0.62
SPEC["texts"] += [{"x": 40, "y": 14, "text": "Agent platform · data flow", "size": "l"},
                 {"x": 40, "y": D_TOP + 236, "text": "Secrets never in the browser: tokens stay in the portal's encrypted cookie; the Langflow key is added by the gateway; provider keys live only in the gateway. Dashed = responses / streams.", "size": "s", "w": 1500}]
if SPEC_OUT:
    json.dump(SPEC, open(SPEC_OUT, "w"), indent=1)
out[0] = out[0].replace("1500", str(H))
out[:] = [o.replace('height="1500"', f'height="{H}"') for o in out]
add("</svg>")
open(OUT, "w").write("\n".join(out))
print("wrote", OUT)
