# Brands

The portal's theme and branding come from `brands/<id>/brand.json`, selected at runtime:

```bash
BRAND=default npm run dev       # or set BRAND in .env.local / the container env
BRAND_DIR=/config/brands         # optional: load brands from a mounted folder instead
```

To add a brand, copy `default/brand.json` to `brands/<id>/brand.json` and change it. No code changes are needed.

| Field | Meaning |
|---|---|
| `name`, `productName` | Header and page title, e.g. "Acme" + "AI Agents" |
| `logo` | Optional `{ light, dark?, alt, height? }`. Paths under `public/` (e.g. `/brands/acme/logo.svg`) or https URLs. Without it, `name` is shown as a text wordmark in the `brand` colour |
| `favicon` | Optional path or https URL |
| `fonts.sans`, `fonts.mono` | CSS font stacks |
| `fonts.faces` | Optional `@font-face` list: `{ family, weight, style?, src: [woff2, woff] }` |
| `radius.card`, `radius.control`, `radius.bubble` | Corner radius of cards and composer, buttons and tags, chat bubbles |
| `colors.light`, `colors.dark` | Every token in `COLOR_TOKENS` (`src/lib/brand.ts`); dark applies with `prefers-color-scheme: dark` |
| `copy` | Signed-out title and text, composer placeholder, optional footer |

Values are checked at startup: a missing token or an unsafe value stops the portal with the file and field name.

Delivery: the brand's tokens and `@font-face` rules are served as `/brand.css?v=<content hash>` with
`Cache-Control: public, max-age=31536000, immutable` (a changed brand gets a new hash; an outdated `v` gets
`no-cache`). The layout also preconnects to external font origins and preloads the regular woff2.
