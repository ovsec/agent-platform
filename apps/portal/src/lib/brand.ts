import "server-only";

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";

// Theme + branding, chosen at runtime: BRAND=<id> loads brands/<id>/brand.json (BRAND_DIR overrides the folder,
// e.g. a mounted ConfigMap). Components only use the CSS variables generated here, never fixed colours.

export const COLOR_TOKENS = [
  "background", // page
  "foreground", // body text
  "surface", // cards, composer
  "muted", // subtle fills: hover, tags, code blocks
  "muted-foreground", // secondary text
  "border",
  "primary", // primary buttons
  "primary-hover",
  "primary-foreground",
  "accent", // links, runtime tag text
  "accent-surface", // runtime tag fill
  "brand", // wordmark colour when there is no logo
  "header-background",
  "header-foreground",
  "user-bubble",
  "user-bubble-foreground",
  "focus-ring",
  "danger",
  "danger-surface",
] as const;
type ColorToken = (typeof COLOR_TOKENS)[number];
type Palette = Record<ColorToken, string>;

type FontFace = { family: string; weight: number; style?: "normal" | "italic"; src: string[] };

export type Brand = {
  id: string;
  name: string; // organisation, e.g. "Acme"
  productName: string; // e.g. "Agent Portal"
  logo?: { light: string; dark?: string; alt: string; height?: number };
  favicon?: string;
  fonts: { sans: string; mono: string; faces?: FontFace[] };
  radius: { card: string; control: string; bubble: string };
  colors: { light: Palette; dark: Palette };
  copy: { signedOutTitle: string; signedOutBody: string; composerPlaceholder: string; footer?: string };
};

// Brand files are trusted config, but they end up inside a <style> tag: refuse anything that could break out.
const SAFE_CSS_VALUE = /^[#a-zA-Z0-9(),.%/'"\s-]+$/;
const SAFE_URL = /^(https:\/\/|\/)[\w\-./~%]+$/;

function check(brand: Brand, file: string): Brand {
  const fail = (msg: string) => {
    throw new Error(`${file}: ${msg}`);
  };
  for (const mode of ["light", "dark"] as const) {
    for (const t of COLOR_TOKENS) {
      const v = brand.colors?.[mode]?.[t];
      if (!v) fail(`colors.${mode}.${t} is missing`);
      if (!SAFE_CSS_VALUE.test(v)) fail(`colors.${mode}.${t} has an invalid value`);
    }
  }
  for (const v of [brand.fonts.sans, brand.fonts.mono, ...Object.values(brand.radius)]) {
    if (!SAFE_CSS_VALUE.test(v)) fail(`invalid font or radius value: ${v}`);
  }
  for (const face of brand.fonts.faces ?? []) {
    if (!SAFE_CSS_VALUE.test(face.family)) fail(`invalid font family: ${face.family}`);
    for (const url of face.src) if (!SAFE_URL.test(url)) fail(`invalid font url: ${url}`);
  }
  for (const url of [brand.logo?.light, brand.logo?.dark, brand.favicon]) {
    if (url && !SAFE_URL.test(url)) fail(`invalid asset url: ${url}`);
  }
  return brand;
}

let cached: Brand | undefined;
export function getBrand(): Brand {
  if (!cached) {
    const dir = process.env.BRAND_DIR ?? path.join(process.cwd(), "brands");
    const id = process.env.BRAND ?? "default";
    if (!/^[a-z0-9-]+$/.test(id)) throw new Error(`invalid BRAND: ${id}`);
    const file = path.join(dir, id, "brand.json");
    cached = check({ id, ...JSON.parse(readFileSync(file, "utf8")) }, file);
  }
  return cached;
}

const vars = (p: Palette) => COLOR_TOKENS.map((t) => `--${t}:${p[t]};`).join("");

/** CSS for the active brand: @font-face rules, light tokens, and dark tokens for prefers-color-scheme: dark. */
export function brandCss(b: Brand): string {
  const faces = (b.fonts.faces ?? [])
    .map(
      (f) =>
        `@font-face{font-family:'${f.family}';font-weight:${f.weight};font-style:${f.style ?? "normal"};` +
        `font-display:swap;src:${f.src.map((u) => `url('${u}') format('${u.endsWith(".woff") ? "woff" : "woff2"}')`).join(",")};}`,
    )
    .join("");
  const shared =
    `--brand-font-sans:${b.fonts.sans};--brand-font-mono:${b.fonts.mono};` +
    `--radius-card:${b.radius.card};--radius-control:${b.radius.control};--radius-bubble:${b.radius.bubble};`;
  return (
    faces +
    `:root{${shared}${vars(b.colors.light)}}` +
    `@media (prefers-color-scheme: dark){:root{${vars(b.colors.dark)}}}`
  );
}

/** Content hash of the active brand CSS: versions /brand.css so browsers can cache it forever. */
export function brandCssVersion(b: Brand): string {
  return createHash("sha256").update(brandCss(b)).digest("hex").slice(0, 12);
}

/** Font hints for <head>: preconnect to external font origins, preload the regular weight (woff2). */
export function brandFontHints(b: Brand): { preconnect: string[]; preload?: string } {
  const faces = b.fonts.faces ?? [];
  const urls = faces.flatMap((f) => f.src).filter((u) => u.startsWith("https://"));
  const preconnect = [...new Set(urls.map((u) => new URL(u).origin))];
  const regular = faces.find((f) => f.weight === 400 && (f.style ?? "normal") === "normal") ?? faces[0];
  const preload = regular?.src.find((u) => u.endsWith(".woff2"));
  return { preconnect, preload };
}
