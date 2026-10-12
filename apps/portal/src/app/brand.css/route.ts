import { brandCss, brandCssVersion, getBrand } from "@/lib/brand";

// The active brand's tokens and @font-face rules as a stylesheet. The layout links /brand.css?v=<content hash>,
// so a matching request is cached for a year; any other version (e.g. an old page after a brand change) is not.
export const dynamic = "force-dynamic"; // BRAND is chosen at runtime, never at build time

export function GET(request: Request) {
  const brand = getBrand();
  const version = brandCssVersion(brand);
  const current = new URL(request.url).searchParams.get("v") === version;
  return new Response(brandCss(brand), {
    headers: {
      "Content-Type": "text/css; charset=utf-8",
      "Cache-Control": current ? "public, max-age=31536000, immutable" : "no-cache",
      ETag: `"${version}"`,
    },
  });
}
