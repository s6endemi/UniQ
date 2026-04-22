"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

const ROOMS = [
  { id: "story", href: "/", label: "Story", hotkey: "1" },
  { id: "start", href: "/start", label: "Start", hotkey: "s" },
  { id: "review", href: "/review", label: "Review", hotkey: "2" },
  { id: "analyst", href: "/analyst", label: "Analyst", hotkey: "3" },
  { id: "platform", href: "/platform", label: "Platform", hotkey: "p" },
] as const;

export function Nav() {
  return (
    <Suspense fallback={<NavShell />}>
      <NavInner />
    </Suspense>
  );
}

function NavShell() {
  // Minimal static mark so the layout doesn't jump during Suspense.
  return (
    <nav className="nav">
      <span className="nav__brand" aria-hidden="true">
        <span className="brand-mark" />
        <span>Uni<em>Q</em></span>
      </span>
      <div className="nav__rooms" />
      <div className="nav__meta" />
    </nav>
  );
}

function NavInner() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  const current = (() => {
    if (pathname === "/") return "story";
    if (pathname.startsWith("/start")) return "start";
    if (pathname.startsWith("/review")) return "review";
    if (pathname.startsWith("/analyst")) return "analyst";
    if (pathname.startsWith("/platform")) return "platform";
    return null;
  })();

  // Which tab should pulse? The guided flow has two handoff moments:
  //   /start + ?step=done   → pulse Review (final sign-off is next)
  //   /substrate-ready      → pulse Analyst (analyst is the first
  //                           consequence of a materialised substrate)
  // The pulse stops the moment the user either clicks the target tab
  // or leaves the handoff page, since it is derived from pathname.
  const pulseTarget: string | null = (() => {
    if (pathname === "/substrate-ready") return "analyst";
    if (pathname.startsWith("/start") && searchParams?.get("step") === "done") {
      return "review";
    }
    return null;
  })();

  // Apply the room-specific paper tone on html element — drives the
  // tonal shift between surfaces documented in DESIGN.md. The guided-
  // demo transition pages (/start, /substrate-ready, /platform) do
  // not have their own tab but still need a non-Story tone so they
  // don't regress to the landing-page paper when rendered.
  useEffect(() => {
    let tone = "var(--story-tone)";
    if (current === "review") tone = "var(--review-tone)";
    else if (current === "analyst") tone = "var(--analyst-tone)";
    else if (
      pathname === "/substrate-ready" ||
      pathname.startsWith("/platform") ||
      pathname.startsWith("/start")
    ) {
      // Warm analyst tone carries across the full guided journey, so
      // the handoff pages feel continuous with the analyst surface.
      tone = "var(--analyst-tone)";
    }
    document.documentElement.style.setProperty("--paper", tone);
  }, [current, pathname]);

  // 1 / 2 / 3 keyboard shortcuts (ignoring when user is typing)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && target.matches("input, textarea")) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const hit = ROOMS.find((r) => r.hotkey === e.key);
      if (hit) router.push(hit.href);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);

  return (
    <nav className="nav">
      <Link href="/" className="nav__brand" aria-label="UniQ home">
        <span className="brand-mark" aria-hidden="true" />
        <span>
          Uni<em>Q</em>
        </span>
      </Link>

      <div className="nav__rooms" role="tablist">
        {ROOMS.map((room) => (
          <Link
            key={room.id}
            href={room.href}
            className="nav__room"
            aria-current={current === room.id}
            data-pulse={pulseTarget === room.id}
          >
            {room.label}
          </Link>
        ))}
      </div>

      <div className="nav__meta">
        <span className="nav__status">
          <span className="nav__status-dot" aria-hidden="true" /> PIPELINE · LIVE
        </span>
      </div>
    </nav>
  );
}
