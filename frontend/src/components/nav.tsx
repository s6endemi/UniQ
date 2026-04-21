"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

const ROOMS = [
  { id: "story", href: "/", label: "Story", hotkey: "1" },
  { id: "review", href: "/review", label: "Review", hotkey: "2" },
  { id: "analyst", href: "/analyst", label: "Analyst", hotkey: "3" },
] as const;

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();

  const current = (() => {
    if (pathname === "/") return "story";
    if (pathname.startsWith("/review")) return "review";
    if (pathname.startsWith("/analyst")) return "analyst";
    return null;
  })();

  // Apply the room-specific paper tone on html element — drives the tonal
  // shift between surfaces documented in DESIGN.md.
  useEffect(() => {
    const tone =
      current === "review"
        ? "var(--review-tone)"
        : current === "analyst"
          ? "var(--analyst-tone)"
          : "var(--story-tone)";
    document.documentElement.style.setProperty("--paper", tone);
  }, [current]);

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
