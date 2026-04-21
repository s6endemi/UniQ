"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArtifactPanel } from "@/components/analyst/artifact-panel";
import { Thinking, type ThinkingStep } from "@/components/analyst/thinking";
import { TypedText } from "@/components/analyst/typed-text";
import {
  PROMPT_SUGGESTIONS,
  matchRecipe,
  type ArtifactDescriptor,
} from "@/lib/demo/recipes";

/**
 * Analyst — conversational surface with artifact-canvas reveal.
 *
 * Orchestrator only: state (turns, draft, busy, current artifact), a
 * scripted "agent" step loop, and the composer. Rendering of every
 * panel lives in `src/components/analyst/*`, scripted demo content
 * lives in `src/lib/demo/recipes.ts`. Phase 6 replaces
 * `matchRecipe(text)` with an HTTP call to /api/uniq/chat (DuckDB-
 * backed agent), while the components and data shapes on this page
 * stay untouched.
 */

interface UserTurn {
  id: number;
  role: "user";
  text: string;
}
interface AiTurn {
  id: number;
  role: "ai";
  phase: "thinking" | "reply";
  steps: ThinkingStep[];
  text?: string;
  artifact?: ArtifactDescriptor;
}
type Turn = UserTurn | AiTurn;

// Pacing constants for the scripted demo. Phase 6 removes these when
// the real agent streams on its own schedule.
const STEP_INTERVAL_MS = 420;
const REVEAL_DELAY_MS = 600;

export default function AnalystPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [artifact, setArtifact] = useState<ArtifactDescriptor | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(0);
  const mkId = () => ++idRef.current;

  useEffect(() => {
    streamRef.current?.scrollTo({
      top: streamRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns]);

  const submit = (q: string) => {
    const text = q.trim();
    if (!text || busy) return;

    const recipe = matchRecipe(text);
    const aiId = mkId();
    const aiTurn: AiTurn = {
      id: aiId,
      role: "ai",
      phase: "thinking",
      steps: recipe.steps.map((t) => ({ text: t, done: false })),
      artifact: recipe.artifact,
    };
    setTurns((t) => [...t, { id: mkId(), role: "user", text }, aiTurn]);
    setDraft("");
    setBusy(true);

    // Fire the real stub endpoint so end-to-end wire stays exercised
    // even while the agent is scripted. Failures are swallowed — the
    // scripted flow runs regardless of backend availability.
    fetch("/api/uniq/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message: text }),
    }).catch(() => undefined);

    recipe.steps.forEach((_, i) => {
      setTimeout(
        () => {
          setTurns((prev) =>
            prev.map((turn) => {
              if (turn.role !== "ai" || turn.id !== aiId) return turn;
              return {
                ...turn,
                steps: turn.steps.map((s, j) =>
                  j <= i ? { ...s, done: true } : s,
                ),
              };
            }),
          );
        },
        STEP_INTERVAL_MS * (i + 1),
      );
    });

    setTimeout(
      () => {
        setTurns((prev) =>
          prev.map((turn) =>
            turn.role === "ai" && turn.id === aiId
              ? { ...turn, phase: "reply", text: recipe.reply }
              : turn,
          ),
        );
        setTimeout(() => {
          setArtifact(recipe.artifact);
          setBusy(false);
        }, REVEAL_DELAY_MS);
      },
      STEP_INTERVAL_MS * (recipe.steps.length + 1),
    );
  };

  const onSend = (e?: FormEvent) => {
    e?.preventDefault();
    submit(draft);
  };

  return (
    <div className="room" data-screen-label="03 Analyst">
      <div className={`analyst ${artifact ? "has-artifact" : ""}`}>
        <div className="chat">
          <div className="chat__stream" ref={streamRef}>
            {turns.length === 0 && (
              <div className="chat__welcome">
                <h1 className="chat__welcome-title">
                  What do you want to <em>know?</em>
                </h1>
                <p className="chat__welcome-sub">
                  Ask in plain language. I&apos;ll query the FHIR substrate
                  and render an artifact beside this conversation.
                </p>
                <div className="chat__suggestions">
                  {PROMPT_SUGGESTIONS.map((s) => (
                    <button
                      key={s.text}
                      type="button"
                      className="chat__suggestion"
                      onClick={() => submit(s.text)}
                    >
                      <span className="t-meta">{s.meta}</span>
                      {s.text}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {turns.map((turn) => {
              if (turn.role === "user") {
                return (
                  <div key={turn.id} className="turn turn--user">
                    <div className="turn__bubble">{turn.text}</div>
                  </div>
                );
              }
              return (
                <div key={turn.id} className="turn turn--ai">
                  <div className="turn__avatar" />
                  <div className="turn__content">
                    <Thinking
                      steps={turn.steps}
                      done={turn.phase === "reply"}
                    />
                    {turn.phase === "reply" && turn.text && (
                      <>
                        <TypedText text={turn.text} />
                        {turn.artifact && (
                          <button
                            type="button"
                            className="turn__artifact-card"
                            onClick={() => setArtifact(turn.artifact!)}
                          >
                            <div className="turn__artifact-thumb" />
                            <div className="turn__artifact-info">
                              <span className="turn__artifact-title">
                                {turn.artifact.title}
                              </span>
                              <span className="turn__artifact-meta">
                                {turn.artifact.subtitle}
                              </span>
                            </div>
                            <span className="turn__artifact-open">Open →</span>
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <form className="composer" onSubmit={onSend}>
            <div className="composer__inner">
              <textarea
                rows={1}
                placeholder="Ask the analyst anything about your data…"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    onSend();
                  }
                }}
                disabled={busy}
              />
              <button
                className="composer__send"
                type="submit"
                disabled={!draft.trim() || busy}
              >
                {busy ? "…" : "Ask →"}
              </button>
            </div>
            <div className="composer__hint">
              queries run against FHIR substrate · 5,374 patients ·
              read-only in preview mode
            </div>
          </form>
        </div>

        {artifact && (
          <ArtifactPanel
            artifact={artifact}
            onClose={() => setArtifact(null)}
          />
        )}
      </div>
    </div>
  );
}
