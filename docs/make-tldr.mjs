// Convert a generic diagram layout (docs/diagram-specs/*.json) into a tldraw file (.tldr).
//
//   npm i @tldraw/tlschema@5.5.2 @tldraw/store@5.5.2 @tldraw/utils@5.5.2   (once, anywhere on NODE_PATH)
//   node docs/make-tldr.mjs docs/diagram-specs/architecture.json docs/architecture.tldr
//
// Layout: { boxes: [{id, x, y, w, h, kind, lines, center?}], zones: [{x, y, w, h, label}],
//           arrows: [{from, to, color, label?, dashed?, fromSide?, toSide?} | {x1, y1, x2, y2, color, label?, dashed?}],
//           lines: [{x, y1, y2}], texts: [{x, y, text, size, w?}] }
// Every record is validated against tldraw's own schema before the file is written.
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { createTLSchema } = require("@tldraw/tlschema");
const { Store } = require("@tldraw/store");
const { getIndexAbove } = require("@tldraw/utils");

const [, , specPath, outPath] = process.argv;
const spec = JSON.parse(readFileSync(specPath, "utf8"));
const SCALE = spec.scale ?? 0.75; // label size ≈ the SVG versions (size "s" = 18px × scale)

const KIND = { // tldraw color, fill, dash
  people: ["black", "none", "solid"], ui: ["blue", "semi", "solid"], idp: ["violet", "semi", "solid"],
  gw: ["blue", "semi", "solid"], "gw-container": ["light-blue", "semi", "solid"], rt: ["green", "semi", "solid"],
  ext: ["orange", "semi", "solid"], dev: ["light-green", "semi", "solid"], data: ["grey", "none", "solid"],
  plan: ["grey", "none", "dashed"], lane: ["black", "none", "solid"],
  "note-req": ["blue", "none", "solid"], "note-hitl": ["red", "none", "solid"],
};
const COLOR = { b: "blue", v: "violet", g: "green", o: "orange", s: "grey", r: "red" };

const richText = (text) => ({
  type: "doc",
  content: text.split("\n").map((line) => (line ? { type: "paragraph", content: [{ type: "text", text: line }] } : { type: "paragraph" })),
});

const records = [
  { id: "document:document", typeName: "document", gridSize: 10, name: "", meta: {} },
  { id: "page:page", typeName: "page", name: "Page 1", index: "a1", meta: {} },
];
let index = "a1";
const nextIndex = () => (index = getIndexAbove(index));
const base = (id, type, x, y) => ({
  id: `shape:${id}`, typeName: "shape", type, x, y, rotation: 0, index: nextIndex(), parentId: "page:page",
  isLocked: false, opacity: 1, meta: {},
});
const geo = (id, x, y, w, h, kind, text, { center = false, zone = false } = {}) => {
  const [color, fill, dash] = zone ? ["grey", "none", "dashed"] : KIND[kind] ?? KIND.data;
  records.push({
    ...base(id, "geo", x, y),
    props: {
      geo: "rectangle", w, h, color, labelColor: zone ? "grey" : "black", fill, dash, size: "s", font: "sans",
      align: center ? "middle" : "start", verticalAlign: center ? "middle" : "start", growY: 0, url: "", scale: SCALE,
      flipX: false, flipY: false, richText: richText(text),
    },
  });
};
const arrowShape = (id, x1, y1, x2, y2, color, label, dashed, kind = "arc", head = "arrow") => {
  records.push({
    ...base(id, "arrow", x1, y1),
    props: {
      kind, labelColor: "black", color: COLOR[color] ?? color, fill: "none", dash: dashed ? "dashed" : "solid", size: "s",
      arrowheadStart: "none", arrowheadEnd: head, font: "sans", start: { x: 0, y: 0 }, end: { x: x2 - x1, y: y2 - y1 },
      bend: 0, richText: richText(label ?? ""), labelPosition: 0.5, scale: SCALE, elbowMidPoint: 0.5,
    },
  });
};
const bind = (arrowId, shapeId, terminal, anchor) => records.push({
  id: `binding:${arrowId}-${terminal}`, typeName: "binding", type: "arrow", fromId: `shape:${arrowId}`, toId: `shape:${shapeId}`,
  props: { terminal, normalizedAnchor: anchor, isExact: false, isPrecise: true, snap: "none" }, meta: {},
});
// anchor on the edge that faces the other box (or as given: "t" | "b" | "l" | "r")
const SIDE = { t: { x: 0.5, y: 0 }, b: { x: 0.5, y: 1 }, l: { x: 0, y: 0.5 }, r: { x: 1, y: 0.5 } };
function sides(f, t) {
  if (t.y >= f.y + f.h) return ["b", "t"];
  if (t.y + t.h <= f.y) return ["t", "b"];
  return t.x >= f.x + f.w ? ["r", "l"] : ["l", "r"];
}

// order matters for stacking: zones, lifelines, boxes, arrows, text
(spec.zones ?? []).forEach((z, i) => geo(`zone${i}`, z.x, z.y, z.w, z.h, "data", z.label, { zone: true }));
(spec.lines ?? []).forEach((l, i) => arrowShape(`life${i}`, l.x, l.y1, l.x, l.y2, "s", "", true, "arc", "none"));
const boxById = {};
for (const b of spec.boxes ?? []) {
  boxById[b.id] = b;
  // tldraw's line height is larger than the SVG's and long lines wrap: make room so labels don't overflow
  const font = 18 * SCALE, perLine = Math.max(8, Math.floor((b.w - 24 * SCALE) / (font * 0.56)));
  const rows = b.lines.reduce((n, line) => n + Math.max(1, Math.ceil(line.length / perLine)), 0);
  const h = Math.max(b.h, 16 * SCALE + rows * font * 1.4);
  geo(b.id, b.x, b.y, b.w, h, b.kind, b.lines.join("\n"), { center: !!b.center });
}
(spec.arrows ?? []).forEach((a, i) => {
  const id = `arrow${i}`;
  if (a.from) {
    const f = boxById[a.from], t = boxById[a.to];
    if (!f || !t) throw new Error(`arrow ${i}: unknown box ${a.from} → ${a.to}`);
    const [fs, ts] = sides(f, t);
    const fa = SIDE[a.fromSide ?? fs], ta = SIDE[a.toSide ?? ts];
    arrowShape(id, f.x + f.w * fa.x, f.y + f.h * fa.y, t.x + t.w * ta.x, t.y + t.h * ta.y, a.color, a.label, a.dashed, "elbow");
    bind(id, a.from, "start", fa);
    bind(id, a.to, "end", ta);
  } else {
    arrowShape(id, a.x1, a.y1, a.x2, a.y2, a.color, a.label, a.dashed);
  }
});
(spec.texts ?? []).forEach((t, i) => records.push({
  ...base(`text${i}`, "text", t.x, t.y),
  props: { color: t.color ?? "black", size: t.size ?? "s", font: "sans", textAlign: "start", w: t.w ?? 900, richText: richText(t.text),
           scale: t.size === "l" ? 0.8 : SCALE, autoSize: !t.w },
}));

// validate with tldraw's schema (throws on any invalid record)
const schema = createTLSchema();
const store = new Store({ schema, props: { defaultName: "", assets: {}, onMount: () => {} } });
store.put(records);
writeFileSync(outPath, JSON.stringify({ tldrawFileFormatVersion: 1, schema: schema.serialize(), records }));
console.log(`wrote ${outPath}: ${records.filter((r) => r.typeName === "shape").length} shapes, ` +
            `${records.filter((r) => r.typeName === "binding").length} bindings (validated)`);
