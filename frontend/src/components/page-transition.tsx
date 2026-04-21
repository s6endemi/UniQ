"use client";

// React ships ViewTransition in its canary type bundle. The runtime
// export exists in the React version Next.js 16 pins; the type tree
// just doesn't surface it unless you opt into the canary profile —
// a reference directive is the least-invasive fix.
/// <reference types="react/canary" />

import { ViewTransition } from "react";
import type { ReactNode } from "react";

/**
 * Page-level transition using React's <ViewTransition> component.
 *
 * Native browser View Transitions API: the browser snapshots the old
 * page, atomically swaps to the new tree, then cross-fades between the
 * two snapshots. React is not re-rendering during the animation, so no
 * double-animate flicker (the problem Framer's AnimatePresence hit in
 * this context).
 *
 * Browsers without View Transitions support (older Safari) still
 * navigate — they just don't animate. No fallback code required.
 */
export function PageTransition({ children }: { children: ReactNode }) {
  return <ViewTransition>{children}</ViewTransition>;
}
