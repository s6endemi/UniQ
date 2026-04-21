"use client";

import { useEffect, useState } from "react";

/**
 * Character-by-character reveal of a fixed text.
 *
 * Starts on mount, runs `setInterval` while typing. `text` is assumed
 * stable across the component's lifetime (one per assistant turn) —
 * parents key on turn id so a new turn mounts a fresh instance rather
 * than mutating this one's prop mid-typing.
 */
export function TypedText({ text }: { text: string }) {
  const [out, setOut] = useState("");

  useEffect(() => {
    let i = 0;
    const id = setInterval(() => {
      i += 2;
      setOut(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(id);
      }
    }, 14);
    return () => clearInterval(id);
  }, [text]);

  const lines = out.split("\n");
  const stillTyping = out.length < text.length;
  return (
    <div className="turn__text">
      {lines.map((line, i) => (
        <p key={i}>
          {line}
          {i === lines.length - 1 && stillTyping && <span className="cursor" />}
        </p>
      ))}
    </div>
  );
}
