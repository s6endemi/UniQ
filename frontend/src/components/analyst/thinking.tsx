"use client";

export interface ThinkingStep {
  text: string;
  done: boolean;
}

/**
 * Perplexity-style thinking panel.
 *
 * Steps tick through from top to bottom — orchestration lives in the
 * parent, this component only renders the current state.
 */
export function Thinking({
  steps,
  done,
}: {
  steps: ThinkingStep[];
  done: boolean;
}) {
  return (
    <div className={`thinking ${done ? "is-done" : ""}`}>
      <div className="thinking__header">
        <span className="thinking__spinner" />
        <span>{done ? `Planned · ${steps.length} steps` : "Thinking…"}</span>
      </div>
      {steps.map((s, i) => (
        <div
          key={`${s.text}-${i}`}
          className={`thinking__step ${s.done ? "is-done" : ""}`}
          style={{ animationDelay: `${i * 50}ms` }}
        >
          <span className="dot" />
          <span>{s.text}</span>
        </div>
      ))}
    </div>
  );
}
