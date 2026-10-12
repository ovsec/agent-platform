import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { LogOut } from "lucide-react";
import { currentSession, signOut } from "@/auth";
import { SessionKeepAlive } from "@/components/session-keep-alive";
import { brandCssVersion, brandFontHints, getBrand, type Brand } from "@/lib/brand";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export function generateMetadata(): Metadata {
  const brand = getBrand();
  return {
    title: `${brand.name} ${brand.productName}`,
    description: "Catalog of AI agents and chat",
    icons: brand.favicon ? { icon: brand.favicon } : undefined,
  };
}

function BrandMark({ brand }: { brand: Brand }) {
  if (brand.logo) {
    const h = brand.logo.height ?? 22;
    return (
      <picture>
        {brand.logo.dark && <source srcSet={brand.logo.dark} media="(prefers-color-scheme: dark)" />}
        <img src={brand.logo.light} alt={brand.logo.alt} style={{ height: h }} />
      </picture>
    );
  }
  return <span className="text-[17px] font-bold tracking-tight text-(--brand)">{brand.name}</span>;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const brand = getBrand();
  const fontHints = brandFontHints(brand);
  const session = await currentSession();
  const userName = session?.user?.name ?? session?.user?.email ?? "";
  return (
    <html lang="en" data-brand={brand.id}>
      <head>
        {fontHints.preconnect.map((origin) => (
          <link key={origin} rel="preconnect" href={origin} crossOrigin="anonymous" />
        ))}
        {fontHints.preload && (
          <link rel="preload" as="font" type="font/woff2" href={fontHints.preload} crossOrigin="anonymous" />
        )}
        {/* brand tokens + @font-face, versioned by content hash and cached for a year */}
        <link rel="stylesheet" href={`/brand.css?v=${brandCssVersion(brand)}`} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <div className="flex h-dvh flex-col">
          <header className="sticky top-0 z-20 border-b border-(--border) bg-(--header-background)/80 text-(--header-foreground) backdrop-blur-md">
            <div className="flex h-14 items-center justify-between px-4 sm:px-6">
              <Link href="/" className="flex items-center gap-2.5">
                <BrandMark brand={brand} />
                <span className="text-sm font-medium text-(--muted-foreground)">{brand.productName}</span>
              </Link>
              {session ? (
                <form
                  action={async () => {
                    "use server";
                    await signOut({ redirectTo: "/" });
                  }}
                  className="flex items-center gap-1"
                >
                  <span className="flex items-center gap-2 rounded-full py-1 pr-2 pl-1 text-sm">
                    <span className="grid size-7 place-items-center rounded-full bg-(--accent-surface) text-[11px] font-semibold text-(--accent)">
                      {initials(userName)}
                    </span>
                    <span className="hidden sm:inline">{userName}</span>
                  </span>
                  <button
                    title="Sign out"
                    aria-label="Sign out"
                    className="grid size-8 place-items-center rounded-full text-(--muted-foreground) transition-colors hover:bg-(--muted) hover:text-(--foreground)"
                  >
                    <LogOut className="size-4" />
                  </button>
                </form>
              ) : null}
            </div>
          </header>
          <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
        </div>
        {session && <SessionKeepAlive />}
      </body>
    </html>
  );
}
