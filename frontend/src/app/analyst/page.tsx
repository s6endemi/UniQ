"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArtifactPanel } from "@/components/analyst/artifact-panel";
import { Thinking, type ThinkingStep } from "@/components/analyst/thinking";
import { TypedText } from "@/components/analyst/typed-text";
import type { ChatArtifact, ChatResponse } from "@/lib/api";
import { PROMPT_SUGGESTIONS, matchRecipe } from "@/lib/demo/recipes";

/**
 * Analyst — conversational surface with artifact-canvas reveal.
 *
 * Phase 6 wired this to the real hybrid-agent endpoint: POST to
 * /api/uniq/chat (proxied to FastAPI, which runs the recipe fast-path
 * or the Claude tool-use loop). The response shape is
 * `ChatResponse { steps, reply, artifact, trace }` — we pace the steps
 * through the Thinking panel so the Perplexity-style reveal still
 * plays even though the backend already did all the work.
 *
 * If the fetch fails (backend down, bad wifi in the pitch room) we
 * fall back to the scripted demo recipes so the surface never turns
 * into an error screen. Both paths produce identical-shaped data, so
 * the rest of the component does not care which one served us.
 */

interface UserTurn {
  id: number;
  role: "user";
  text: string;
}
interface AiTurn {
  id: number;
  role: "ai";
  phase: "thinking" | "reply" | "error";
  steps: ThinkingStep[];
  text?: string;
  artifact?: ChatArtifact | null;
  errorMessage?: string;
}
type Turn = UserTurn | AiTurn;

type ChatOutcome =
  | { kind: "ok"; response: ChatResponse }
  | { kind: "error"; message: string };

// Pacing constants — kept tight enough to feel live, loose enough that
// a three-step plan still reads as deliberate rather than dumped.
const STEP_INTERVAL_MS = 420;
const REVEAL_DELAY_MS = 600;

export default function AnalystPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [artifact, setArtifact] = useState<ChatArtifact | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(0);
  const mkId = () => ++idRef.current;

  useEffect(() => {
    streamRef.current?.scrollTo({
      top: streamRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns]);

  const submit = async (q: string) => {
    const text = q.trim();
    if (!text || busy) return;

    const aiId = mkId();
    // We do not know the step list until the response lands, so the
    // thinking panel starts with a placeholder and rewrites itself
    // when the backend answers. This is the only place where steps
    // mutate mid-turn; the `id === aiId` filter keeps us from leaking
    // across concurrent turns.
    const aiTurn: AiTurn = {
      id: aiId,
      role: "ai",
      phase: "thinking",
      steps: [
        { text: "Thinking…", done: false },
      ],
    };
    setTurns((t) => [...t, { id: mkId(), role: "user", text }, aiTurn]);
    setDraft("");
    setBusy(true);

    const outcome = await fetchChat(text);

    if (outcome.kind === "error") {
      // Surface the failure honestly — no scripted cover-up. A convincing
      // fake dashboard on a real backend error is worse than an error
      // message, especially in front of a clinical audience.
      setTurns((prev) =>
        prev.map((turn) =>
          turn.role === "ai" && turn.id === aiId
            ? {
                ...turn,
                phase: "error",
                steps: [{ text: "Request failed", done: true }],
                errorMessage: outcome.message,
              }
            : turn,
        ),
      );
      setBusy(false);
      return;
    }

    const response = outcome.response;

    // Replace placeholder with real steps, then tick them through.
    setTurns((prev) =>
      prev.map((turn) =>
        turn.role === "ai" && turn.id === aiId
          ? {
              ...turn,
              steps: response.steps.map((s) => ({ text: s, done: false })),
              artifact: response.artifact,
            }
          : turn,
      ),
    );

    response.steps.forEach((_, i) => {
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
              ? { ...turn, phase: "reply", text: response.reply }
              : turn,
          ),
        );
        setTimeout(() => {
          if (response.artifact) {
            setArtifact(response.artifact);
          }
          setBusy(false);
        }, REVEAL_DELAY_MS);
      },
      STEP_INTERVAL_MS * (response.steps.length + 1),
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
                      done={turn.phase !== "thinking"}
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
                    {turn.phase === "error" && (
                      <div className="turn__error" role="alert">
                        <span className="turn__error-label">Backend error</span>
                        <span className="turn__error-detail">
                          {turn.errorMessage ?? "The analyst is unreachable."}
                        </span>
                      </div>
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
              queries run against FHIR substrate · read-only in preview mode
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

/**
 * Call the BFF and classify the outcome.
 *
 * Fallback rules (intentionally strict so the UI never fabricates
 * answers under failure):
 *
 *   HTTP response received (2xx or non-2xx)
 *     └── 2xx → ok, use the backend's ChatResponse
 *     └── non-2xx → error, show the status to the user; NEVER script
 *         over a backend bug, because the scripted answer would be
 *         unrelated to what the user asked.
 *
 *   Fetch threw (network unreachable, DNS, CORS, etc.)
 *     └── matchRecipe hits → ok with the scripted response (genuine
 *         pitch-room wifi safety; only the 3 golden-path prompts
 *         qualify, and their scripted output is on-topic).
 *     └── no match → error. We refuse to dress up a random question
 *         with a Mounjaro dashboard just because there is nothing
 *         better to show.
 */
async function fetchChat(message: string): Promise<ChatOutcome> {
  let res: Response;
  try {
    res = await fetch("/api/uniq/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
      cache: "no-store",
    });
  } catch {
    const scripted = matchRecipe(message);
    if (scripted) return { kind: "ok", response: scripted };
    return {
      kind: "error",
      message:
        "The analyst backend is unreachable and no offline demo matches this question.",
    };
  }

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`.trim();
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* not JSON — keep status text */
    }
    return { kind: "error", message: detail };
  }

  return { kind: "ok", response: (await res.json()) as ChatResponse };
}
