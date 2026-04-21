"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Story" },
  { href: "/review", label: "Review" },
  { href: "/analyst", label: "Analyst" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 border-b border-ink-700/60 bg-ink-950/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2 font-display text-lg font-semibold tracking-tight">
          <span className="relative inline-block h-2 w-2 rounded-full bg-glacial">
            <span className="absolute inset-0 animate-ping rounded-full bg-glacial opacity-60" />
          </span>
          <span>Uni</span>
          <span className="text-glacial">Q</span>
        </Link>

        <div className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-ink-800 text-text-0"
                    : "text-text-2 hover:bg-ink-800/60 hover:text-text-1"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </div>

        <div className="flex items-center gap-3 text-xs text-text-3 font-mono">
          <span className="hidden sm:inline">v0.1</span>
        </div>
      </div>
    </nav>
  );
}
